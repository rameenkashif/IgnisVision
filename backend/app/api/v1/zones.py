import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.models import User, Zone, ZoneAssessment
from app.schemas.incidents import AssessmentOut, ZoneOut, ZoneUpdate
from app.services import incidents as svc

router = APIRouter(tags=["zones"])
Reader = Annotated[User, Depends(require_roles("incident_commander", "admin"))]
Commander = Annotated[User, Depends(require_roles("incident_commander"))]


async def _zone(db: DB, zone_id: uuid.UUID) -> Zone:
    zone = await db.get(Zone, zone_id)
    if zone is None:
        raise AppError(404, "zone_not_found")
    await svc.get_incident(db, zone.incident_id)  # 404 if the incident was deleted
    return zone


@router.get("/incidents/{incident_id}/zones", response_model=list[ZoneOut])
async def list_zones(incident_id: uuid.UUID, _: Reader, db: DB) -> list[ZoneOut]:
    return (await svc.load_detail(db, await svc.get_incident(db, incident_id))).zones


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
async def update_zone(zone_id: uuid.UUID, body: ZoneUpdate, _: Commander, db: DB) -> ZoneOut:
    zone = await _zone(db, zone_id)
    if "label" in body.model_fields_set:
        zone.label = body.label or None
    await db.commit()
    inc = await svc.get_incident(db, zone.incident_id)
    await svc.publish_incident(db, inc)
    detail = await svc.load_detail(db, inc)
    return next(z for z in detail.zones if z.id == zone.id)


@router.get("/zones/{zone_id}/assessments", response_model=list[AssessmentOut])
async def zone_assessments(
    zone_id: uuid.UUID, _: Reader, db: DB, limit: int = Query(default=50, ge=1, le=500)
) -> list[ZoneAssessment]:
    """Zone risk history, newest first (SRS UC-05 postcondition)."""
    await _zone(db, zone_id)
    rows = await db.execute(
        select(ZoneAssessment)
        .where(ZoneAssessment.zone_id == zone_id)
        .order_by(ZoneAssessment.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())
