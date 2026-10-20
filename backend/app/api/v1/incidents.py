"""Incidents. Phase 1 ships the read-only list so RBAC is enforced from day one;
create/dispatch/close arrive in Phase 3."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.deps import DB, require_roles
from app.models import Incident, User

router = APIRouter(prefix="/incidents", tags=["incidents"])

# Commanders run incidents; admins have read access (HANDOFF §6). Trainees etc. get 403.
IncidentReader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]


class IncidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    address: str | None
    city: str | None
    structure_type: str
    incident_type: str
    status: str
    source: str
    opened_at: datetime
    closed_at: datetime | None


class IncidentList(BaseModel):
    items: list[IncidentSummary]
    total: int


@router.get("", response_model=IncidentList)
async def list_incidents(
    _: IncidentReader,
    db: DB,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IncidentList:
    stmt = select(Incident).where(Incident.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Incident.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(stmt.order_by(Incident.opened_at.desc()).limit(limit).offset(offset))
    return IncidentList(
        items=[IncidentSummary.model_validate(r) for r in rows.scalars()], total=total
    )
