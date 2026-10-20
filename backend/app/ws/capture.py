"""Zone capture stream (HANDOFF §7.3): phone camera JPEGs in, zone results out.
Latest-frame-wins: only the newest frame is kept; a backlog is never queued."""

import asyncio
import contextlib
import logging
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.capture import zone_for_capture
from app.db.engine import SessionLocal
from app.events.bus import bus, incident_channel
from app.ml.registry import capture_started
from app.models import CaptureSession, Zone
from app.services import settings as settings_svc
from app.services.alerts import create_alert, publish_alert
from app.services.zone_pipeline import PERSIST_EVERY_S, FrameError, process_frame
from app.ws.auth import FORBIDDEN, WsReject, authenticate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ws")
active_sessions: set[uuid.UUID] = set()


async def _session_event(session: CaptureSession, zone: Zone, state: str) -> None:
    await bus.publish(
        incident_channel(session.incident_id),
        {
            "type": "capture.session",
            "session": {
                "id": str(session.id),
                "zone_id": str(zone.id),
                "zone_code": zone.code,
                "user_id": str(session.user_id),
                "state": state,
                "frames_received": session.frames_received,
                "frames_analysed": session.frames_analysed,
            },
        },
    )


@router.websocket("/capture")
async def capture(ws: WebSocket) -> None:
    await ws.accept()
    session_id: uuid.UUID | None = None
    zone: Zone | None = None
    stopped_cleanly = False
    try:
        user = await authenticate(ws)
        start = await ws.receive_json()
        if not isinstance(start, dict) or start.get("type") != "start":
            raise WsReject(4400, "start_required")
        try:
            zone_id = uuid.UUID(str(start.get("zone_id")))
        except ValueError as e:
            raise WsReject(4400, "invalid_zone") from e
        async with SessionLocal() as db:
            zone = await zone_for_capture(db, user, zone_id)
            if zone is None:
                raise WsReject(FORBIDDEN, "zone_not_capturable")
            fps = float((await settings_svc.load_all(db))["capture_fps"])
            session = CaptureSession(incident_id=zone.incident_id, zone_id=zone.id, user_id=user.id)
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id
        active_sessions.add(session_id)
        capture_started()
        await ws.send_json(
            {"type": "started", "session_id": str(session_id), "target_fps": fps,
             "zone_code": zone.code}
        )  # fmt: skip
        await _session_event(session, zone, "started")

        latest: dict[str, bytes | None] = {"frame": None}
        has_frame = asyncio.Event()
        received = 0

        async def receive() -> None:
            nonlocal received, stopped_cleanly
            while True:
                msg = await ws.receive()
                if msg["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(msg.get("code", 1000))
                if msg.get("bytes") is not None:
                    received += 1
                    latest["frame"] = msg["bytes"]  # overwrite: latest frame wins
                    has_frame.set()
                elif msg.get("text"):
                    if '"stop"' in msg["text"]:
                        stopped_cleanly = True
                        return
                    if '"ping"' in msg["text"]:
                        await ws.send_json({"type": "pong"})

        async def analyse() -> None:
            last_persist = 0.0
            while True:
                await has_frame.wait()
                has_frame.clear()
                frame, latest["frame"] = latest["frame"], None
                if frame is None:
                    continue
                persist = time.monotonic() - last_persist >= PERSIST_EVERY_S
                async with SessionLocal() as db:
                    s = await db.get(CaptureSession, session_id)
                    s.frames_received = received
                    try:
                        outcome = await process_frame(
                            db, zone_id=zone.id, jpeg=frame, session=s, persist=persist
                        )
                    except FrameError as e:
                        await ws.send_json({"type": "error", "code": str(e)})
                        continue
                if persist:
                    last_persist = time.monotonic()
                await ws.send_json(outcome.message())
                for a in outcome.alerts:
                    await ws.send_json(
                        {"type": "alert", "severity": a.severity, "alert_type": a.type,
                         "message_key": a.message_key, "params": a.message_params}
                    )  # fmt: skip

        tasks = [asyncio.create_task(receive()), asyncio.create_task(analyse())]
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
    except WsReject as r:
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "code": r.reason})
            await ws.close(code=r.code, reason=r.reason)
    except WebSocketDisconnect:
        pass
    finally:
        if session_id is not None:
            # Shielded: the server may cancel this task when the client vanishes, and the
            # session end + camera_lost alert must still be written.
            await asyncio.shield(asyncio.ensure_future(_finish(session_id, zone, stopped_cleanly)))
            if stopped_cleanly:
                with contextlib.suppress(Exception):
                    await ws.close(1000)


async def _finish(session_id: uuid.UUID, zone: Zone, stopped_cleanly: bool) -> None:
    active_sessions.discard(session_id)
    try:
        async with SessionLocal() as db:
            s = await db.get(CaptureSession, session_id)
            s.ended_at = datetime.now(UTC)
            alert = None
            if not stopped_cleanly:
                alert = await create_alert(
                    db,
                    incident_id=s.incident_id,
                    zone_id=s.zone_id,
                    severity="info",
                    type="camera_lost",
                    message_key="alerts.camera_lost",
                    params={"zone": zone.code},
                    commit=False,
                )
            await db.commit()
            if alert is not None:
                await publish_alert(alert)
            await _session_event(s, zone, "ended")
    except Exception:
        log.exception("failed to close capture session %s", session_id)
