import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import DB, require_roles
from app.models import Incident, TeamAssignment, User, Zone
from app.schemas.incidents import IncidentSummary, ZoneOut
from app.services import incidents as svc

router = APIRouter(prefix="/capture", tags=["capture"])
Capturer = Annotated[User, Depends(require_roles("incident_commander", "field_responder"))]


class TargetZone(ZoneOut):
    assigned_to_me: bool


class CaptureTarget(BaseModel):
    incident: IncidentSummary
    assigned_to_me: bool
    zones: list[TargetZone]


@router.get("/targets", response_model=list[CaptureTarget])
async def capture_targets(user: Capturer, db: DB) -> list[CaptureTarget]:
    """Zones the user may stream: any zone of an active incident; own assignments first."""
    incidents = (
        (
            await db.execute(
                select(Incident)
                .where(Incident.status == "active", Incident.deleted_at.is_(None))
                .order_by(Incident.activated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    mine = set(
        (
            await db.execute(
                select(TeamAssignment.zone_id).where(
                    TeamAssignment.user_id == user.id, TeamAssignment.unassigned_at.is_(None)
                )
            )
        ).scalars()
    )
    out = []
    for inc in incidents:
        detail = await svc.load_detail(db, inc)
        zones = [TargetZone(**z.model_dump(), assigned_to_me=z.id in mine) for z in detail.zones]
        zones.sort(key=lambda z: (not z.assigned_to_me,))
        out.append(
            CaptureTarget(
                incident=IncidentSummary.model_validate(inc),
                assigned_to_me=any(z.assigned_to_me for z in zones),
                zones=zones,
            )
        )
    out.sort(key=lambda t: not t.assigned_to_me)
    return out


async def zone_for_capture(db, user: User, zone_id: uuid.UUID) -> Zone | None:
    """Commanders and responders may capture any zone of an active incident (HANDOFF §6)."""
    if user.role not in ("incident_commander", "field_responder"):
        return None
    zone = await db.get(Zone, zone_id)
    if zone is None:
        return None
    inc = await db.get(Incident, zone.incident_id)
    if inc is None or inc.deleted_at is not None or inc.status != "active":
        return None
    return zone
