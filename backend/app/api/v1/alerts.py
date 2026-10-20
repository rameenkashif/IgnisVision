import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.events.bus import bus, incident_channel
from app.models import Alert, User
from app.schemas.incidents import AlertList, AlertOut, Severity
from app.services import incidents as svc

router = APIRouter(tags=["alerts"])
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]


@router.get("/incidents/{incident_id}/alerts", response_model=AlertList)
async def list_alerts(
    incident_id: uuid.UUID,
    _: Reader,
    db: DB,
    severity: list[Severity] | None = Query(default=None),
    unacknowledged: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AlertList:
    await svc.get_incident(db, incident_id)
    stmt = select(Alert).where(Alert.incident_id == incident_id)
    if severity:
        stmt = stmt.where(Alert.severity.in_(severity))
    if unacknowledged:
        stmt = stmt.where(Alert.acknowledged_at.is_(None))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset))
    return AlertList(items=[AlertOut.model_validate(a) for a in rows.scalars()], total=total)


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
async def acknowledge(alert_id: uuid.UUID, commander: Commander, db: DB) -> AlertOut:
    alert = await db.get(Alert, alert_id)
    if alert is None:
        raise AppError(404, "alert_not_found")
    await svc.get_incident(db, alert.incident_id)
    if alert.acknowledged_at is None:
        alert.acknowledged_at = svc.now()
        alert.acknowledged_by = commander.id
        await db.commit()
        await db.refresh(alert)
    out = AlertOut.model_validate(alert)
    await bus.publish(
        incident_channel(alert.incident_id),
        {"type": "alert.acknowledged", "alert": out.model_dump(mode="json")},
    )
    return out
