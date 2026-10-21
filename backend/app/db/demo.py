"""A closed demo incident so Reports and the dashboard have content on first run (HANDOFF §5).
Idempotent via incidents.client_uuid = DEMO_KEY."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    Floor,
    Incident,
    Station,
    TeamAssignment,
    ThermalDetection,
    User,
    Victim,
    Zone,
    ZoneAssessment,
)
from app.services import incidents as incidents_svc
from app.services import reports as reports_svc
from app.services import rpi as rpi_svc
from app.services import settings as settings_svc

DEMO_KEY = "seed-demo-incident-0001"
MODELS = {"mock-segformer": "mock-1.0", "mock-yolo-seg": "mock-1.0"}

# zone code → [(minutes after activation, status)]
HISTORY = {
    "F1-Z1": [(2, "safe"), (34, "safe")],
    "F1-Z2": [(3, "safe"), (11, "caution"), (14, "unsafe"), (40, "unsafe")],
    "F1-Z3": [(5, "caution"), (30, "caution")],
    "F1-Z4": [(6, "safe")],
    "F2-Z1": [(8, "caution"), (21, "blocked")],
    "F2-Z2": [(9, "safe"), (25, "caution")],
    "F2-Z3": [],
    "F2-Z4": [(12, "safe")],
}
PEOPLE = [  # zone, posture, posture conf, detection conf, minutes
    ("F1-Z2", "lying", 0.86, 0.91, 16),
    ("F2-Z1", "sitting", 0.72, 0.84, 22),
    ("F1-Z3", "bending", 0.55, 0.77, 27),
    ("F2-Z2", "standing", 0.9, 0.69, 29),
]


async def seed_demo_incident(db: AsyncSession, station: Station) -> str:
    existing = (
        await db.execute(select(Incident).where(Incident.client_uuid == DEMO_KEY))
    ).scalar_one_or_none()
    if existing is not None:
        return f"{existing.code} (already present)"
    users = {
        u.username: u
        for u in (
            await db.execute(
                select(User).where(func.lower(User.username).in_(["commander1", "responder1"]))
            )
        )
        .scalars()
        .unique()
    }
    commander, responder = users.get("commander1"), users.get("responder1")
    values = await settings_svc.load_all(db)
    t0 = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=10, minute=12, second=0, microsecond=0
    )
    act = t0 + timedelta(minutes=9)
    at = lambda m: act + timedelta(minutes=m)  # noqa: E731

    inc = Incident(
        station_id=station.id, code=await incidents_svc.next_code(db),
        address="Gul Plaza, M.A. Jinnah Road (demo)", city="Lahore", structure_type="commercial",
        incident_type="structural", reported_by="Rescue 1122 control room", status="closed",
        commander_id=commander.id if commander else None, opened_at=t0, activated_at=act,
        closed_at=at(52), closed_by=commander.id if commander else None, source="web",
        client_uuid=DEMO_KEY,
        summary_text="Demo data created by the seed script for training and screenshots.",
    )  # fmt: skip
    db.add(inc)
    await db.flush()
    zones: dict[str, Zone] = {}
    for f in (1, 2):
        floor = Floor(incident_id=inc.id, number=f, label=f"F{f}")
        db.add(floor)
        await db.flush()
        for z in range(1, 5):
            code = f"F{f}-Z{z}"
            zones[code] = Zone(
                incident_id=inc.id, floor_id=floor.id, code=code, grid_row=f - 1, grid_col=z - 1,
                label={"F1-Z1": "Lobby", "F2-Z1": "Stairwell"}.get(code),
            )  # fmt: skip
            db.add(zones[code])
    await db.flush()

    for code, steps in HISTORY.items():
        zone, last = zones[code], None
        for minute, status in steps:
            a = ZoneAssessment(
                zone_id=zone.id, status=status, risk_score={"safe": 0.1, "caution": 0.4,
                "unsafe": 0.75, "blocked": 0.95}[status], confidence=0.82, analysable=True,
                reasons=[], model_versions=MODELS, created_at=at(minute),
            )  # fmt: skip
            db.add(a)
            await db.flush()
            last = a
        if last:
            zone.current_status, zone.current_assessment_id = last.status, last.id
            zone.status_updated_at = last.created_at

    if responder:
        db.add_all([
            TeamAssignment(incident_id=inc.id, zone_id=zones["F1-Z2"].id, user_id=responder.id,
                           device_label="Rig 1", assigned_at=t0 + timedelta(minutes=3),
                           unassigned_at=at(18), assigned_by=commander.id if commander else None),
            TeamAssignment(incident_id=inc.id, zone_id=zones["F2-Z1"].id, user_id=responder.id,
                           device_label="Rig 1", assigned_at=at(18), unassigned_at=at(52),
                           assigned_by=commander.id if commander else None),
        ])  # fmt: skip

    for i, (code, posture, pconf, dconf, minute) in enumerate(PEOPLE, start=1):
        env = rpi_svc.env_risk_from_zone(
            next((s for m, s in reversed(HISTORY[code]) if m <= minute), None)
        )
        r = rpi_svc.compute(posture=posture, posture_confidence=pconf, detection_confidence=dconf,
                            env_risk=env, settings=values)  # fmt: skip
        det = ThermalDetection(
            incident_id=inc.id, zone_id=zones[code].id, bbox=[0.3, 0.4, 0.55, 0.9],
            posture=posture, posture_confidence=pconf, low_confidence=r.low_confidence,
            detection_confidence=dconf, env_risk=env, rpi_score=r.score, rpi_band=r.band,
            source="web_upload", track_id=i, detected_at=at(minute),
            model_versions={"mock-yolo-pose": "mock-1.0"},
        )  # fmt: skip
        db.add(det)
        await db.flush()
        db.add(
            Victim(
                incident_id=inc.id, zone_id=zones[code].id, track_key=f"demo:{i}",
                best_detection_id=det.id, latest_posture=posture, latest_rpi_score=r.score,
                latest_rpi_band=r.band, first_seen_at=at(minute), last_seen_at=at(minute + 2),
                status="rescued" if i <= 2 else "detected", source="web_upload",
            )
        )  # fmt: skip

    for minute, sev, kind, params, code in [
        (14, "crit", "zone_rapid_change", {"from": "caution", "to": "unsafe"}, "F1-Z2"),
        (16, "crit", "victim_critical", {}, "F1-Z2"),
        (21, "crit", "zone_blocked", {}, "F2-Z1"),
        (33, "info", "analysis_failed", {}, "F2-Z3"),
    ]:
        db.add(
            Alert(
                incident_id=inc.id, zone_id=zones[code].id, severity=sev, type=kind,
                message_key=f"alerts.{kind}", message_params={"zone": code, **params},
                acknowledged_by=commander.id if commander and sev == "crit" else None,
                acknowledged_at=at(minute + 1) if sev == "crit" else None, created_at=at(minute),
            )
        )  # fmt: skip
    await db.flush()
    await reports_svc.compile_and_store(db, inc, commander.id if commander else None)
    return f"{inc.code} (created)"
