"""Live channels (HANDOFF §7.2). The client reconnects with backoff and refetches the
incident aggregate after every (re)connect, so missed events are never a problem."""

import asyncio
import contextlib
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import exists, select

from app.db.engine import SessionLocal
from app.events.bus import STATION, bus, incident_channel
from app.models import Incident, TeamAssignment, User
from app.ws.auth import FORBIDDEN, NOT_FOUND, WsReject, authenticate

router = APIRouter(prefix="/ws")
PING_EVERY_S = 25


async def _can_watch_incident(user: User, incident_id: uuid.UUID) -> bool:
    async with SessionLocal() as db:
        inc = await db.get(Incident, incident_id)
        if inc is None or inc.deleted_at is not None:
            raise WsReject(NOT_FOUND, "incident_not_found")
        if user.role in ("incident_commander", "admin"):
            return True
        if user.role != "field_responder":
            return False
        # Responders: their own incident, or any active incident (HANDOFF §6, zone capture).
        if inc.status == "active":
            return True
        assigned = await db.execute(
            select(
                exists().where(
                    TeamAssignment.incident_id == incident_id,
                    TeamAssignment.user_id == user.id,
                    TeamAssignment.unassigned_at.is_(None),
                )
            )
        )
        return bool(assigned.scalar())


async def _pump(ws: WebSocket, channel: str, hello: dict) -> None:
    async with bus.subscribe(channel) as events:
        await ws.send_json(hello)

        async def forward() -> None:
            async for event in events:
                await ws.send_json(event)

        async def receive() -> None:
            while True:
                msg = await ws.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "ping":
                    await ws.send_json({"type": "pong"})

        async def keepalive() -> None:
            while True:
                await asyncio.sleep(PING_EVERY_S)
                await ws.send_json({"type": "ping"})

        tasks = [asyncio.create_task(c()) for c in (forward, receive, keepalive)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if (exc := t.exception()) and not isinstance(exc, WebSocketDisconnect):
                    raise exc
        finally:
            for t in tasks:
                t.cancel()
            for t in tasks:
                with contextlib.suppress(BaseException):
                    await t


async def _serve(ws: WebSocket, run) -> None:
    await ws.accept()
    try:
        await run()
    except WsReject as r:
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "code": r.reason})
            await ws.close(code=r.code, reason=r.reason)
    except WebSocketDisconnect:
        pass


@router.websocket("/incidents/{incident_id}")
async def incident_stream(ws: WebSocket, incident_id: uuid.UUID) -> None:
    async def run() -> None:
        user = await authenticate(ws)
        if not await _can_watch_incident(user, incident_id):
            raise WsReject(FORBIDDEN, "forbidden")
        await _pump(
            ws, incident_channel(incident_id), {"type": "ready", "incident_id": str(incident_id)}
        )

    await _serve(ws, run)


@router.websocket("/station")
async def station_stream(ws: WebSocket) -> None:
    """Station-wide incident list changes (created / status / deleted) for dashboards."""

    async def run() -> None:
        user = await authenticate(ws)
        if user.role not in ("incident_commander", "admin"):
            raise WsReject(FORBIDDEN, "forbidden")
        await _pump(ws, STATION, {"type": "ready"})

    await _serve(ws, run)
