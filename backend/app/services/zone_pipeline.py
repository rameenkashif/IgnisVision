"""RGB frame → zone assessment (HANDOFF §9.3): both segmenters in parallel on the ML pool →
fusion → persist (insert-only history) → zone status → alerts → live events."""

import asyncio
import io
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import bus, incident_channel
from app.ml import runtime
from app.ml.registry import get_models
from app.models import Alert, CaptureSession, Incident, Zone, ZoneAssessment
from app.services import alerts as alerts_svc
from app.services import incidents as incidents_svc
from app.services import settings as settings_svc
from app.services.media import media_url, store_media
from app.services.overlay import render_overlay
from app.services.zone_fusion import FusionResult, fuse

MAX_FRAME_BYTES = 2_000_000
MAX_WIDTH = 1280
PERSIST_EVERY_S = 5.0  # keep a sampled frame at least this often, and on every status change
SEVERE = ("unsafe", "blocked")


class FrameError(ValueError):
    pass


def decode_jpeg(data: bytes) -> np.ndarray:
    if len(data) > MAX_FRAME_BYTES:
        raise FrameError("frame_too_large")
    if not data.startswith(b"\xff\xd8"):
        raise FrameError("not_jpeg")
    try:
        img = Image.open(io.BytesIO(data))
        img.draft("RGB", (MAX_WIDTH, MAX_WIDTH))
        img = img.convert("RGB")
    except Exception as e:
        raise FrameError("undecodable_frame") from e
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, int(img.height * MAX_WIDTH / img.width)))
    return np.asarray(img)


@dataclass
class FrameOutcome:
    zone_id: uuid.UUID
    zone_code: str
    result: FusionResult
    status: str  # zone status after this frame (previous one kept when not analysable)
    assessment_id: uuid.UUID
    frame_url: str | None
    overlay_url: str | None
    alerts: list[Alert] = field(default_factory=list)
    latency_ms: int = 0

    def message(self) -> dict[str, Any]:
        r = self.result
        return {
            "type": "zone_result",
            "zone_id": str(self.zone_id),
            "zone_code": self.zone_code,
            "status": self.status,
            "analysable": r.analysable,
            "risk_score": r.risk_score,
            "confidence": r.confidence,
            "reasons": r.reasons,
            "damage": r.damage,
            "frame_url": self.frame_url,
            "overlay_url": self.overlay_url,
            "latency_ms": self.latency_ms,
        }


async def _rapid_change_from(
    db: AsyncSession, zone_id: uuid.UUID, window_s: int, before: datetime
) -> str | None:
    """Was the zone safe/caution within the window? Then a jump to unsafe/blocked is 'rapid'."""
    row = await db.execute(
        select(ZoneAssessment.status)
        .where(
            ZoneAssessment.zone_id == zone_id,
            ZoneAssessment.analysable.is_(True),
            ZoneAssessment.status.in_(("safe", "caution")),
            ZoneAssessment.created_at >= before - timedelta(seconds=window_s),
        )
        .order_by(ZoneAssessment.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def _recent_failure_alert(db: AsyncSession, zone_id: uuid.UUID, interval_s: int) -> bool:
    row = await db.execute(
        select(Alert.id)
        .where(
            Alert.zone_id == zone_id,
            Alert.type == "analysis_failed",
            Alert.created_at >= datetime.now(UTC) - timedelta(seconds=interval_s),
        )
        .limit(1)
    )
    return row.first() is not None


async def process_frame(
    db: AsyncSession,
    *,
    zone_id: uuid.UUID,
    jpeg: bytes,
    session: CaptureSession | None = None,
    persist: bool = True,
) -> FrameOutcome:
    t0 = time.perf_counter()
    image = await runtime.run(decode_jpeg, jpeg)
    models = get_models()
    seg, damage = await asyncio.gather(
        runtime.run(models.segmenter.predict, image),
        runtime.run(models.damage.predict, image),
    )
    values = await settings_svc.load_all(db)
    result = fuse(seg, damage, values["zone_fusion"])

    zone = (await db.execute(select(Zone).where(Zone.id == zone_id).with_for_update())).scalar_one()
    inc = await db.get(Incident, zone.incident_id)
    now = datetime.now(UTC)
    stale_s = int(values["stale_zone_seconds"])
    prev_status, _ = incidents_svc.effective_status(zone, now, stale_s)
    new_status = result.status if result.analysable else zone.current_status
    changed = result.analysable and new_status != prev_status

    frame_id = overlay_id = None
    if persist or changed:
        base = f"incidents/{inc.id}/zones/{zone.id}/{now:%Y%m%dT%H%M%S%f}"
        h, w = image.shape[:2]
        frame = await store_media(
            db,
            key=f"{base}.jpg",
            data=jpeg,
            kind="rgb_frame",
            mime="image/jpeg",
            source="capture",
            incident_id=inc.id,
            width=w,
            height=h,
            uploaded_by=session.user_id if session else None,
        )
        png = await runtime.run(render_overlay, seg, result.damage)
        overlay = await store_media(
            db,
            key=f"{base}.overlay.png",
            data=png,
            kind="rgb_frame",
            mime="image/png",
            source="capture",
            incident_id=inc.id,
        )
        frame_id, overlay_id = frame.id, overlay.id

    assessment = ZoneAssessment(
        zone_id=zone.id,
        capture_session_id=session.id if session else None,
        media_id=frame_id,
        overlay_media_id=overlay_id,
        status=result.status,
        risk_score=result.risk_score,
        confidence=result.confidence,
        analysable=result.analysable,
        reasons=result.reasons,
        segmentation_summary=result.segmentation_summary,
        damage_instances=result.damage,
        model_versions=models.versions(),
    )
    db.add(assessment)
    await db.flush()

    new_alerts: list[Alert] = []
    params = {"zone": zone.code}
    if result.analysable:
        if new_status in SEVERE and changed:
            rapid_from = await _rapid_change_from(
                db, zone.id, int(values["rapid_change_window_s"]), now
            )
            if rapid_from:
                new_alerts.append(
                    await alerts_svc.create_alert(
                        db,
                        incident_id=inc.id,
                        zone_id=zone.id,
                        severity="crit",
                        type="zone_rapid_change",
                        message_key="alerts.zone_rapid_change",
                        params={**params, "from": rapid_from, "to": new_status},
                        commit=False,
                    )
                )
            else:
                kind = "zone_blocked" if new_status == "blocked" else "zone_unsafe"
                new_alerts.append(
                    await alerts_svc.create_alert(
                        db,
                        incident_id=inc.id,
                        zone_id=zone.id,
                        severity="crit" if new_status == "blocked" else "warn",
                        type=kind,
                        message_key=f"alerts.{kind}",
                        params=params,
                        commit=False,
                    )
                )
        zone.current_status = new_status
        zone.current_assessment_id = assessment.id
        zone.status_updated_at = now
    elif not await _recent_failure_alert(
        db, zone.id, int(values["analysis_failed_alert_interval_s"])
    ):
        new_alerts.append(
            await alerts_svc.create_alert(
                db,
                incident_id=inc.id,
                zone_id=zone.id,
                severity="info",
                type="analysis_failed",
                message_key="alerts.analysis_failed",
                params=params,
                commit=False,
            )
        )

    if session:
        session.frames_analysed += 1
    await db.commit()

    # Frame URLs: this frame if stored, else the zone's latest stored one.
    if frame_id is None and zone.current_assessment_id:
        latest = await db.get(ZoneAssessment, zone.current_assessment_id)
        if latest and latest.media_id:
            frame_id, overlay_id = latest.media_id, latest.overlay_media_id
    outcome = FrameOutcome(
        zone_id=zone.id,
        zone_code=zone.code,
        result=result,
        status=new_status,
        assessment_id=assessment.id,
        frame_url=media_url(frame_id),
        overlay_url=media_url(overlay_id),
        alerts=new_alerts,
        latency_ms=int(1000 * (time.perf_counter() - t0)),
    )

    channel = incident_channel(inc.id)
    await bus.publish(
        channel,
        {
            "type": "zone.updated",
            "zone_id": str(zone.id),
            "status": new_status,
            "analysable": result.analysable,
            "risk_score": result.risk_score,
            "confidence": result.confidence,
            "assessment_id": str(assessment.id),
            "frame_url": outcome.frame_url,
            "overlay_url": outcome.overlay_url,
            "at": now.isoformat(),
        },
    )
    for a in new_alerts:
        await alerts_svc.publish_alert(a)
    await incidents_svc.publish_incident(db, inc)
    return outcome
