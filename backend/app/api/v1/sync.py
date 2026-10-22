"""Mobile sync (HANDOFF §7.4). The Flutter app uploads incidents recorded offline. Idempotent
per client_uuid (and per client_detection_uuid for detections added to a linked web incident).
RPI is recomputed with the server's current settings; the phone's value is kept in
meta.mobile_rpi for comparison."""

import io
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.models import Incident, MediaAsset, SyncBatch, ThermalDetection, User, Victim
from app.schemas.thermal import SyncIncident, SyncPayload, SyncResponse, SyncResult
from app.services import incidents as incidents_svc
from app.services import rpi as rpi_svc
from app.services import settings as settings_svc
from app.services import victims as victims_svc
from app.services.alerts import publish_alert
from app.storage.backend import get_storage

router = APIRouter(prefix="/sync", tags=["mobile sync"])
MobileUser = Annotated[User, Depends(require_roles("field_responder", "incident_commander"))]
MAX_FRAME_BYTES = 10 * 1024 * 1024


async def _parse(request: Request) -> tuple[SyncPayload, dict[str, UploadFile]]:
    ctype = request.headers.get("content-type", "")
    frames: dict[str, UploadFile] = {}
    try:
        if ctype.startswith("multipart/form-data"):
            form = await request.form(max_files=2000)
            raw = form.get("payload")
            if raw is None:
                raise AppError(422, "payload_missing")
            text = raw if isinstance(raw, str) else (await raw.read()).decode()
            payload = SyncPayload.model_validate(json.loads(text))
            for name, value in form.multi_items():
                if isinstance(value, UploadFile) and name != "payload":
                    frames[value.filename or name] = value
        else:
            payload = SyncPayload.model_validate(await request.json())
    except ValidationError as e:
        raise AppError(422, "validation_failed", {"fields": e.errors(include_url=False)}) from e
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise AppError(422, "invalid_json") from e
    return payload, frames


async def _store_frame(db: DB, inc_id: uuid.UUID, user: User, f: UploadFile) -> MediaAsset:
    data = await f.read()
    if len(data) > MAX_FRAME_BYTES or not (data[:2] == b"\xff\xd8" or data[:4] == b"\x89PNG"):
        raise ValueError("bad_frame")
    mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
    media_id = uuid.uuid4()
    key = f"incidents/{inc_id}/mobile/{media_id}{'.png' if mime == 'image/png' else '.jpg'}"
    size, sha = get_storage().save_stream(key, io.BytesIO(data), MAX_FRAME_BYTES)
    asset = MediaAsset(
        id=media_id, incident_id=inc_id, kind="thermal_image", storage_key=key, mime=mime,
        bytes=size, sha256=sha, uploaded_by=user.id, source="mobile_sync",
    )  # fmt: skip
    db.add(asset)
    await db.flush()
    return asset


async def _sync_one(
    db: DB, user: User, item: SyncIncident, frames: dict[str, UploadFile], values: dict
) -> SyncResult:
    linked = None
    if item.linked_incident_id:
        linked = await incidents_svc.get_incident(db, item.linked_incident_id)
    else:
        dup = (
            await db.execute(select(Incident).where(Incident.client_uuid == item.client_uuid))
        ).scalar_one_or_none()
        if dup is not None:
            return SyncResult(client_uuid=item.client_uuid, status="duplicate", incident_id=dup.id)

    existing_ids = set()
    if item.detections:
        existing_ids = set(
            (
                await db.execute(
                    select(ThermalDetection.client_detection_uuid).where(
                        ThermalDetection.client_detection_uuid.in_(
                            [d.client_detection_uuid for d in item.detections]
                        )
                    )
                )
            ).scalars()
        )
    new_dets = [d for d in item.detections if d.client_detection_uuid not in existing_ids]
    if linked is not None and item.detections and not new_dets:
        return SyncResult(client_uuid=item.client_uuid, status="duplicate", incident_id=linked.id)

    inc = linked
    if inc is None:
        inc = Incident(
            station_id=user.station_id, code=await incidents_svc.next_code(db),
            address=item.label, reported_by=user.full_name,
            status="closed" if item.ended_at else "active", commander_id=None,
            opened_at=item.started_at, activated_at=item.started_at, closed_at=item.ended_at,
            source="mobile_sync", client_uuid=item.client_uuid,
        )  # fmt: skip
        db.add(inc)
        await db.flush()

    media_by_ref: dict[str, MediaAsset] = {}
    rows: list[ThermalDetection] = []
    for d in new_dets:
        media = None
        if d.frame_ref and d.frame_ref in frames:
            if d.frame_ref not in media_by_ref:
                media_by_ref[d.frame_ref] = await _store_frame(
                    db, inc.id, user, frames[d.frame_ref]
                )
            media = media_by_ref[d.frame_ref]
        r = rpi_svc.compute(
            posture=d.posture, posture_confidence=d.posture_confidence,
            detection_confidence=d.detection_confidence, env_risk=d.env_risk, settings=values,
            low_confidence=d.low_confidence or None,
        )  # fmt: skip
        row = ThermalDetection(
            incident_id=inc.id, media_id=media.id if media else None, track_id=d.track_id,
            bbox=[float(x) for x in d.bbox], keypoints=d.keypoints, posture=d.posture,
            posture_confidence=d.posture_confidence, low_confidence=r.low_confidence,
            detection_confidence=d.detection_confidence, env_risk=d.env_risk,
            rpi_score=r.score, rpi_band=r.band, source="mobile_sync",
            client_detection_uuid=d.client_detection_uuid, detected_at=d.captured_at,
            meta={"mobile_rpi": d.rpi_score, "mobile_band": d.rpi_band, "mode": d.mode,
                  "frame_ref": d.frame_ref},
        )  # fmt: skip
        db.add(row)
        rows.append(row)
    await db.flush()

    # One victim per (sync incident, track id); untracked detections are individual people.
    groups: dict[str, list[ThermalDetection]] = {}
    for row, d in zip(rows, new_dets, strict=True):
        person = d.track_id if d.track_id is not None else d.client_detection_uuid
        key = f"mobile:{item.client_uuid}:{person}"
        groups.setdefault(key, []).append(row)
    touched, alerts = [], []
    for key, obs in groups.items():
        existing = (
            await db.execute(
                select(Victim).where(Victim.incident_id == inc.id, Victim.track_key == key)
            )
        ).scalar_one_or_none()
        if existing is not None:
            prev = (
                (
                    await db.execute(
                        select(ThermalDetection).where(
                            ThermalDetection.id == existing.best_detection_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            obs = obs + list(prev)
        v, alert = await victims_svc.upsert_track(
            db, incident_id=inc.id, zone_id=None, zone_code=None, track_key=key,
            observations=obs, source="mobile_sync", existing=existing,
        )  # fmt: skip
        touched.append(v)
        if alert:
            alerts.append(alert)
    await db.commit()
    for v in touched:
        await victims_svc.publish(db, v)
    for a in alerts:
        await publish_alert(a)
    await incidents_svc.publish_incident(db, inc, created=linked is None)
    return SyncResult(client_uuid=item.client_uuid, status="created", incident_id=inc.id)


@router.post("/incidents", response_model=SyncResponse)
async def sync_incidents(request: Request, user: MobileUser, db: DB) -> SyncResponse:
    """application/json, or multipart/form-data with a `payload` JSON part plus thermal frame
    parts whose filenames match `frame_ref`. A duplicate returns 200 with status "duplicate"."""
    payload, frames = await _parse(request)
    values = await settings_svc.load_all(db)
    batch = SyncBatch(
        user_id=user.id, device_id=payload.device_id, app_version=payload.app_version,
        incident_count=len(payload.incidents), status="processing",
    )  # fmt: skip
    db.add(batch)
    await db.commit()
    batch_id = batch.id  # objects expire on rollback; keep the key
    results = []
    for item in payload.incidents:
        try:
            results.append(await _sync_one(db, user, item, frames, values))
        except AppError as e:
            await db.rollback()
            results.append(SyncResult(client_uuid=item.client_uuid, status="error", error=e.code))
        except ValueError as e:
            await db.rollback()
            results.append(SyncResult(client_uuid=item.client_uuid, status="error", error=str(e)))
    batch = await db.get(SyncBatch, batch_id)
    batch.status = "error" if any(r.status == "error" for r in results) else "done"
    batch.error = "; ".join(f"{r.client_uuid}: {r.error}" for r in results if r.error) or None
    await db.commit()
    return SyncResponse(results=results)
