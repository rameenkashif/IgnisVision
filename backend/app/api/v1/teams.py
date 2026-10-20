import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DB, CurrentUser, require_roles
from app.core.errors import AppError
from app.events.bus import bus, incident_channel
from app.models import Incident, TeamAssignment, User, Zone
from app.schemas.incidents import AssignmentCreate, AssignmentOut, MyAssignment, ResponderOut
from app.services import incidents as svc

router = APIRouter(tags=["teams"])
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]


async def _publish_change(db: DB, inc: Incident, changed: list[AssignmentOut]) -> None:
    for a in changed:
        await bus.publish(
            incident_channel(inc.id),
            {"type": "assignment.changed", "assignment": a.model_dump(mode="json")},
        )
    await svc.publish_incident(db, inc)


@router.get("/incidents/{incident_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(
    incident_id: uuid.UUID, _: Reader, db: DB, include_history: bool = False
) -> list[AssignmentOut]:
    await svc.get_incident(db, incident_id)
    return await svc.assignments_for(db, incident_id, include_history=include_history)


@router.post("/incidents/{incident_id}/assignments", response_model=AssignmentOut, status_code=201)
async def assign(
    incident_id: uuid.UUID, body: AssignmentCreate, commander: Commander, db: DB
) -> AssignmentOut:
    """Assign a responder to a zone. If already assigned in this incident, this is a
    reassignment: the old row is closed (history kept), a new one opened (SRS UC-07 AF)."""
    inc = await svc.get_incident(db, incident_id, lock=True)
    if inc.status == "closed":
        raise AppError(409, "incident_closed")
    user = await svc.check_responder(db, body.user_id)
    zone_code = None
    if body.zone_id:
        zone = await db.get(Zone, body.zone_id)
        if zone is None or zone.incident_id != inc.id:
            raise AppError(422, "zone_not_in_incident")
        zone_code = zone.code
    t = svc.now()
    changed: list[AssignmentOut] = []
    existing = await db.execute(
        select(TeamAssignment).where(
            TeamAssignment.incident_id == inc.id,
            TeamAssignment.user_id == user.id,
            TeamAssignment.unassigned_at.is_(None),
        )
    )
    codes = dict(
        (await db.execute(select(Zone.id, Zone.code).where(Zone.incident_id == inc.id))).all()
    )
    for old in existing.scalars():
        old.unassigned_at = t
        changed.append(svc.assignment_out(old, user, codes.get(old.zone_id)))
    new = TeamAssignment(
        incident_id=inc.id,
        zone_id=body.zone_id,
        user_id=user.id,
        device_label=body.device_label or None,
        assigned_by=commander.id,
        assigned_at=t,
    )
    db.add(new)
    await db.commit()
    await db.refresh(new)
    out = svc.assignment_out(new, user, zone_code)
    await _publish_change(db, inc, [*changed, out])
    return out


@router.delete("/assignments/{assignment_id}", response_model=AssignmentOut)
async def unassign(assignment_id: uuid.UUID, _: Commander, db: DB) -> AssignmentOut:
    a = await db.get(TeamAssignment, assignment_id)
    if a is None:
        raise AppError(404, "assignment_not_found")
    inc = await svc.get_incident(db, a.incident_id, lock=True)
    if a.unassigned_at is None:
        a.unassigned_at = svc.now()
    await db.commit()
    user = await db.get(User, a.user_id)
    zone = await db.get(Zone, a.zone_id) if a.zone_id else None
    out = svc.assignment_out(a, user, zone.code if zone else None)
    await _publish_change(db, inc, [out])
    return out


@router.get("/assignments/mine", response_model=list[MyAssignment])
async def my_assignments(user: CurrentUser, db: DB) -> list[MyAssignment]:
    """A responder's own current assignments ("own assignment only", HANDOFF §6)."""
    rows = await db.execute(
        select(TeamAssignment, Incident, Zone)
        .join(Incident, Incident.id == TeamAssignment.incident_id)
        .outerjoin(Zone, Zone.id == TeamAssignment.zone_id)
        .where(
            TeamAssignment.user_id == user.id,
            TeamAssignment.unassigned_at.is_(None),
            Incident.deleted_at.is_(None),
            Incident.status != "closed",
        )
        .order_by(TeamAssignment.assigned_at.desc())
    )
    return [
        MyAssignment(
            **svc.assignment_out(a, user, z.code if z else None).model_dump(),
            incident_code=inc.code,
            incident_status=inc.status,
        )
        for a, inc, z in rows.all()
    ]


@router.get("/responders", response_model=list[ResponderOut])
async def list_responders(_: Commander, db: DB) -> list[ResponderOut]:
    """Active field responders for the dispatch form, with their current open incident."""
    users = (
        (
            await db.execute(
                select(User)
                .where(User.role == "field_responder", User.is_active.is_(True))
                .order_by(User.full_name)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    busy = dict(
        (
            await db.execute(
                select(TeamAssignment.user_id, Incident.code)
                .join(Incident, Incident.id == TeamAssignment.incident_id)
                .where(
                    TeamAssignment.unassigned_at.is_(None),
                    Incident.status != "closed",
                    Incident.deleted_at.is_(None),
                )
            )
        ).all()
    )
    return [
        ResponderOut(
            id=u.id, full_name=u.full_name, username=u.username, active_incident_code=busy.get(u.id)
        )
        for u in users
    ]
