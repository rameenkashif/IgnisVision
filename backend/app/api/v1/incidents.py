import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.events.bus import STATION, bus, incident_channel
from app.models import Incident, TeamAssignment, User
from app.schemas.incidents import (
    IncidentCreate,
    IncidentDetail,
    IncidentList,
    IncidentStatus,
    IncidentSummary,
    IncidentUpdate,
)
from app.schemas.users import Confirm
from app.services import audit
from app.services import incidents as svc

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Commanders run incidents; admins have read access (HANDOFF §6). Trainees etc. get 403.
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]
Admin = Annotated[User, Depends(require_roles("admin"))]


def _snapshot(inc: Incident) -> dict:
    return IncidentSummary.model_validate(inc).model_dump(mode="json")


@router.get("", response_model=IncidentList)
async def list_incidents(
    _: Reader,
    db: DB,
    status: list[IncidentStatus] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IncidentList:
    stmt = select(Incident).where(Incident.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Incident.status.in_(status))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Incident.code).like(like),
                func.lower(Incident.address).like(like),
                func.lower(Incident.city).like(like),
            )
        )
    if from_:
        stmt = stmt.where(Incident.opened_at >= from_)
    if to:
        stmt = stmt.where(Incident.opened_at <= to)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(stmt.order_by(Incident.opened_at.desc()).limit(limit).offset(offset))
    return IncidentList(
        items=[IncidentSummary.model_validate(r) for r in rows.scalars()], total=total
    )


@router.post("", response_model=IncidentDetail, status_code=201)
async def create_incident(body: IncidentCreate, commander: Commander, db: DB) -> IncidentDetail:
    """Dispatch modal: incident, floors, zones and team assignments in one transaction."""
    inc = await svc.create_incident(db, body, commander)
    await db.commit()
    await svc.publish_incident(db, inc, created=True)
    return await svc.load_detail(db, inc)


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: uuid.UUID, _: Reader, db: DB) -> IncidentDetail:
    return await svc.load_detail(db, await svc.get_incident(db, incident_id))


@router.patch("/{incident_id}", response_model=IncidentDetail)
async def update_incident(
    incident_id: uuid.UUID, body: IncidentUpdate, _: Commander, db: DB
) -> IncidentDetail:
    inc = await svc.get_incident(db, incident_id, lock=True)
    changes = body.model_dump(exclude_unset=True)
    if inc.status == "closed" and set(changes) - {"summary_text"}:
        raise AppError(409, "incident_closed")
    for k, v in changes.items():
        setattr(inc, k, v)
    await db.commit()
    await svc.publish_incident(db, inc)
    return await svc.load_detail(db, inc)


@router.post("/{incident_id}/activate", response_model=IncidentDetail)
async def activate_incident(incident_id: uuid.UUID, _: Commander, db: DB) -> IncidentDetail:
    """Briefing → live (teams on site, operations begin)."""
    inc = await svc.get_incident(db, incident_id, lock=True)
    if inc.status not in ("draft", "dispatched"):
        raise AppError(409, "invalid_status_transition", {"from": inc.status, "to": "active"})
    inc.status = "active"
    inc.activated_at = svc.now()
    await db.commit()
    await svc.publish_incident(db, inc)
    return await svc.load_detail(db, inc)


@router.post("/{incident_id}/close", response_model=IncidentDetail)
async def close_incident(
    incident_id: uuid.UUID, body: Confirm, commander: Commander, db: DB
) -> IncidentDetail:
    if not body.confirm:
        raise AppError(400, "confirmation_required")
    inc = await svc.get_incident(db, incident_id, lock=True)
    if inc.status == "closed":
        raise AppError(409, "invalid_status_transition", {"from": "closed", "to": "closed"})
    t = svc.now()
    inc.status = "closed"
    inc.closed_at = t
    inc.closed_by = commander.id
    # End active assignments (history kept); this also ends the idle-timeout exemption.
    rows = await db.execute(
        select(TeamAssignment).where(
            TeamAssignment.incident_id == inc.id, TeamAssignment.unassigned_at.is_(None)
        )
    )
    for a in rows.scalars():
        a.unassigned_at = t
    # Report compilation is attached here in Phase 6.
    await db.commit()
    await svc.publish_incident(db, inc)
    return await svc.load_detail(db, inc)


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(
    incident_id: uuid.UUID, body: Confirm, request: Request, admin: Admin, db: DB
) -> None:
    """Admin-only soft delete with confirmation and audit (SRS §5.5.3)."""
    if not body.confirm:
        raise AppError(400, "confirmation_required")
    inc = await svc.get_incident(db, incident_id, lock=True)
    before = _snapshot(inc)
    inc.deleted_at = svc.now()
    await audit.record(
        db,
        actor_id=admin.id,
        action="incident.delete",
        entity_type="incident",
        entity_id=inc.id,
        before=before,
        request=request,
    )
    await db.commit()
    await bus.publish(STATION, {"type": "incident.deleted", "incident_id": str(inc.id)})
    await bus.publish(
        incident_channel(inc.id), {"type": "incident.deleted", "incident_id": str(inc.id)}
    )
