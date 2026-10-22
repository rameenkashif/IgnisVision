import uuid
from datetime import datetime

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.bus import bus, incident_channel
from app.models import Alert, MediaAsset, ThermalDetection, Victim, Zone
from app.schemas.thermal import VictimOut
from app.services import alerts as alerts_svc
from app.services.media import media_url

BAND_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}


async def detection_frame_url(db: AsyncSession, d: ThermalDetection) -> str | None:
    """Signed URL of the stored sampled frame for a detection in an uploaded video."""
    if d.media_id is None or d.frame_index is None:
        return None
    media = await db.get(MediaAsset, d.media_id)
    if media is None or media.kind != "thermal_video":
        return None
    return media_url(d.media_id, f"/frames/{d.frame_index}")


async def victim_out(db: AsyncSession, v: Victim) -> VictimOut:
    best = await db.get(ThermalDetection, v.best_detection_id) if v.best_detection_id else None
    zone = await db.get(Zone, v.zone_id) if v.zone_id else None
    return VictimOut(
        id=v.id,
        incident_id=v.incident_id,
        zone_id=v.zone_id,
        zone_code=zone.code if zone else None,
        track_key=v.track_key,
        posture=v.latest_posture,
        posture_confidence=best.posture_confidence if best else None,
        low_confidence=bool(best and best.low_confidence),
        detection_confidence=best.detection_confidence if best else None,
        rpi_score=v.latest_rpi_score,
        rpi_band=v.latest_rpi_band,
        env_risk=best.env_risk if best else None,
        status=v.status,
        source=v.source,
        first_seen_at=v.first_seen_at,
        last_seen_at=v.last_seen_at,
        best_detection_id=v.best_detection_id,
        media_id=best.media_id if best else None,
        media_url=media_url(best.media_id) if best and best.media_id else None,
        frame_url=await detection_frame_url(db, best) if best else None,
        timestamp_ms=best.timestamp_ms if best else None,
        bbox=best.bbox if best else None,
    )


async def ranked(db: AsyncSession, incident_id: uuid.UUID) -> list[VictimOut]:
    """Detected people first, by highest RPI; rescued after; false positives last."""
    status_order = case((Victim.status == "detected", 0), (Victim.status == "rescued", 1), else_=2)
    rows = await db.execute(
        select(Victim)
        .where(Victim.incident_id == incident_id)
        .order_by(status_order, Victim.latest_rpi_score.desc(), Victim.first_seen_at)
    )
    return [await victim_out(db, v) for v in rows.scalars()]


async def upsert_track(
    db: AsyncSession,
    *,
    incident_id: uuid.UUID,
    zone_id: uuid.UUID | None,
    zone_code: str | None,
    track_key: str,
    observations: list[ThermalDetection],
    source: str,
    existing: Victim | None,
) -> tuple[Victim, Alert | None]:
    """Create/update the aggregated person. Ranking uses the highest-RPI observation; posture
    shown is the latest one. Returns (victim, critical alert if it just became critical)."""
    best = max(observations, key=lambda d: d.rpi_score)
    latest = max(observations, key=lambda d: (d.timestamp_ms or 0, d.detected_at))
    first: datetime = min(d.detected_at for d in observations)
    last: datetime = max(d.detected_at for d in observations)
    was_critical = existing is not None and existing.latest_rpi_band == "critical"
    v = existing or Victim(
        incident_id=incident_id, zone_id=zone_id, track_key=track_key, source=source,
        first_seen_at=first,
    )  # fmt: skip
    if existing is None or best.rpi_score >= (existing.latest_rpi_score or 0):
        v.best_detection_id = best.id
        v.latest_rpi_score = best.rpi_score
        v.latest_rpi_band = best.rpi_band
    v.latest_posture = latest.posture
    v.first_seen_at = min(v.first_seen_at or first, first)
    v.last_seen_at = max(v.last_seen_at or last, last)
    if existing is None:
        db.add(v)
    await db.flush()
    alert = None
    if v.latest_rpi_band == "critical" and not was_critical:
        alert = await alerts_svc.create_alert(
            db, incident_id=incident_id, zone_id=zone_id, severity="crit",
            type="victim_critical", message_key="alerts.victim_critical",
            params={"zone": zone_code or "—"}, commit=False,
        )  # fmt: skip
    return v, alert


async def publish(db: AsyncSession, v: Victim) -> None:
    out = await victim_out(db, v)
    await bus.publish(
        incident_channel(v.incident_id),
        {"type": "victim.upserted", "victim": out.model_dump(mode="json")},
    )
