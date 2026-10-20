"""Incident aggregate, KPIs and the stale-zone rule (HANDOFF §5, §8.2)."""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.events.bus import STATION, bus, incident_channel
from app.models import (
    Floor,
    Incident,
    TeamAssignment,
    User,
    Victim,
    Zone,
    ZoneAssessment,
)
from app.schemas.incidents import (
    AssignmentOut,
    FloorOut,
    IncidentCreate,
    IncidentDetail,
    IncidentSummary,
    Kpis,
    UserRef,
    ZoneOut,
)
from app.services import settings as settings_svc

SEVERITY_ORDER = {"safe": 0, "caution": 1, "unsafe": 2, "blocked": 3}


def now() -> datetime:
    return datetime.now(UTC)


def effective_status(zone: Zone, at: datetime, stale_s: int) -> tuple[str, bool]:
    """A zone is never presented as safe without a current analysis (SRS §5.2.3, §5.5.2)."""
    if zone.status_updated_at is None or zone.current_status == "unclassified":
        return "unclassified", False
    if at - zone.status_updated_at > timedelta(seconds=stale_s):
        return "unclassified", True
    return zone.current_status, False


async def next_code(db: AsyncSession) -> str:
    n = (await db.execute(text("SELECT nextval('incident_code_seq')"))).scalar_one()
    return f"IV-{now().year}-{n:04d}"


async def get_incident(db: AsyncSession, incident_id: uuid.UUID, *, lock: bool = False) -> Incident:
    q = select(Incident).where(Incident.id == incident_id, Incident.deleted_at.is_(None))
    if lock:
        q = q.with_for_update()
    inc = (await db.execute(q)).scalar_one_or_none()
    if inc is None:
        raise AppError(404, "incident_not_found")
    return inc


async def check_responder(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.role != "field_responder":
        raise AppError(422, "assignee_not_responder", {"user_id": str(user_id)})
    return user


async def create_incident(db: AsyncSession, body: IncidentCreate, commander: User) -> Incident:
    inc = Incident(
        station_id=commander.station_id,
        code=await next_code(db),
        address=body.address,
        city=body.city,
        structure_type=body.structure_type,
        incident_type=body.incident_type,
        reported_by=body.reported_by,
        status="dispatched",
        commander_id=commander.id,
        source="web",
    )
    db.add(inc)
    await db.flush()

    zones_by_code: dict[str, Zone] = {}
    for f in range(1, body.floors + 1):
        floor = Floor(incident_id=inc.id, number=f, label=f"F{f}")
        db.add(floor)
        await db.flush()
        for z in range(1, body.zones_per_floor + 1):
            code = f"F{f}-Z{z}"
            zone = Zone(
                incident_id=inc.id,
                floor_id=floor.id,
                code=code,
                label=body.zone_labels.get(code) or None,
                grid_row=f - 1,
                grid_col=z - 1,
                current_status="unclassified",
            )
            db.add(zone)
            zones_by_code[code] = zone
    await db.flush()

    for a in body.assignments:
        await check_responder(db, a.user_id)
        db.add(
            TeamAssignment(
                incident_id=inc.id,
                zone_id=zones_by_code[a.zone_code].id if a.zone_code else None,
                user_id=a.user_id,
                device_label=a.device_label or None,
                assigned_by=commander.id,
            )
        )
    await db.flush()
    return inc


async def _users(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    rows = (await db.execute(select(User).where(User.id.in_(ids)))).scalars().unique()
    return {u.id: u for u in rows}


def assignment_out(a: TeamAssignment, user: User, zone_code: str | None) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        incident_id=a.incident_id,
        zone_id=a.zone_id,
        zone_code=zone_code,
        user=UserRef.model_validate(user),
        device_label=a.device_label,
        assigned_at=a.assigned_at,
        unassigned_at=a.unassigned_at,
        assigned_by=a.assigned_by,
    )


async def assignments_for(
    db: AsyncSession, incident_id: uuid.UUID, *, include_history: bool = False
) -> list[AssignmentOut]:
    q = select(TeamAssignment).where(TeamAssignment.incident_id == incident_id)
    if not include_history:
        q = q.where(TeamAssignment.unassigned_at.is_(None))
    rows = list((await db.execute(q.order_by(TeamAssignment.assigned_at))).scalars())
    users = await _users(db, {a.user_id for a in rows})
    codes = dict(
        (await db.execute(select(Zone.id, Zone.code).where(Zone.incident_id == incident_id))).all()
    )
    return [assignment_out(a, users[a.user_id], codes.get(a.zone_id)) for a in rows]


async def load_detail(db: AsyncSession, inc: Incident) -> IncidentDetail:
    values = await settings_svc.load_all(db)
    stale_s = int(values["stale_zone_seconds"])
    threshold = int(values["evacuation_threshold_pct"])
    t = now()

    floors = list(
        (
            await db.execute(
                select(Floor).where(Floor.incident_id == inc.id).order_by(Floor.number)
            )
        ).scalars()
    )
    floor_num = {f.id: f.number for f in floors}
    zones = list(
        (
            await db.execute(
                select(Zone)
                .where(Zone.incident_id == inc.id)
                .order_by(Zone.grid_row, Zone.grid_col)
            )
        ).scalars()
    )
    assessment_ids = {z.current_assessment_id for z in zones if z.current_assessment_id}
    assessments = {}
    if assessment_ids:
        rows = await db.execute(select(ZoneAssessment).where(ZoneAssessment.id.in_(assessment_ids)))
        assessments = {a.id: a for a in rows.scalars()}

    assignments = await assignments_for(db, inc.id)
    by_zone: dict[uuid.UUID, list[UserRef]] = defaultdict(list)
    for a in assignments:
        if a.zone_id:
            by_zone[a.zone_id].append(a.user)

    victim_counts = dict(
        (
            await db.execute(
                select(Victim.zone_id, func.count())
                .where(Victim.incident_id == inc.id, Victim.status != "false_positive")
                .group_by(Victim.zone_id)
            )
        ).all()
    )

    zone_out: list[ZoneOut] = []
    counts = {s: 0 for s in ("unclassified", "safe", "caution", "unsafe", "blocked")}
    confidences: list[float] = []
    for z in zones:
        status, stale = effective_status(z, t, stale_s)
        counts[status] += 1
        a = assessments.get(z.current_assessment_id) if z.current_assessment_id else None
        if a and status != "unclassified":
            confidences.append(a.confidence)
        zone_out.append(
            ZoneOut(
                id=z.id,
                floor_id=z.floor_id,
                floor_number=floor_num[z.floor_id],
                code=z.code,
                label=z.label,
                grid_row=z.grid_row,
                grid_col=z.grid_col,
                status=status,
                stored_status=z.current_status,
                stale=stale,
                status_updated_at=z.status_updated_at,
                risk_score=a.risk_score if a else None,
                confidence=a.confidence if a else None,
                assessment_id=z.current_assessment_id,
                assignees=by_zone.get(z.id, []),
                victim_count=victim_counts.get(z.id, 0),
            )
        )

    total = len(zones)
    classified = total - counts["unclassified"]
    worst = max(
        (s for s in SEVERITY_ORDER if counts[s]), key=SEVERITY_ORDER.__getitem__, default=None
    )
    evac_ok = (
        round(100 * (counts["safe"] + counts["caution"]) / classified, 1) if classified else None
    )
    commander = await db.get(User, inc.commander_id) if inc.commander_id else None
    kpis = Kpis(
        zones_total=total,
        zones_by_status=counts,
        classified=classified,
        building_status=worst or "unclassified",
        evac_ok_pct=evac_ok,
        unclassified_pct=round(100 * counts["unclassified"] / total, 1) if total else 100.0,
        evacuation_threshold_pct=threshold,
        below_threshold=evac_ok is not None and evac_ok < threshold,
        victims_detected=sum(victim_counts.values()),
        response_units=len({a.user.id for a in assignments}),
        ai_confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
        stale_zone_seconds=stale_s,
    )
    return IncidentDetail(
        **IncidentSummary.model_validate(inc).model_dump(),
        commander=UserRef.model_validate(commander) if commander else None,
        summary_text=inc.summary_text,
        floors=[FloorOut.model_validate(f) for f in floors],
        zones=zone_out,
        assignments=assignments,
        kpis=kpis,
    )


async def publish_incident(db: AsyncSession, inc: Incident, *, created: bool = False) -> None:
    """Push the new state to the incident channel and the station-wide list channel."""
    detail = await load_detail(db, inc)
    payload = detail.model_dump(mode="json")
    await bus.publish(incident_channel(inc.id), {"type": "incident.updated", "incident": payload})
    summary = IncidentSummary.model_validate(inc).model_dump(mode="json")
    kind = "incident.created" if created else "incident.updated"
    await bus.publish(STATION, {"type": kind, "incident": summary})
