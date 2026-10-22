import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.deps import DB, require_roles
from app.models import AuditLog, User

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_roles("admin"))]


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: Any | None
    created_at: datetime
    actor_username: str | None = None
    actor_name: str | None = None


class AuditList(BaseModel):
    items: list[AuditOut]
    total: int


class AuditFacets(BaseModel):
    actions: list[str]
    entity_types: list[str]


@router.get("/audit-logs", response_model=AuditList)
async def audit_logs(
    _: Admin,
    db: DB,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditList:
    stmt = select(AuditLog)
    for col, val in (
        (AuditLog.entity_type, entity_type),
        (AuditLog.entity_id, entity_id),
        (AuditLog.actor_user_id, actor_user_id),
        (AuditLog.action, action),
    ):
        if val is not None:
            stmt = stmt.where(col == val)
    if from_ is not None:
        stmt = stmt.where(AuditLog.created_at >= from_)
    if to is not None:
        stmt = stmt.where(AuditLog.created_at <= to)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(
        stmt.add_columns(User.username, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = []
    for log, username, name in rows.all():
        item = AuditOut.model_validate(log)
        item.ip = None if item.ip is None else str(item.ip)
        item.actor_username, item.actor_name = username, name
        items.append(item)
    return AuditList(items=items, total=total)


@router.get("/audit-logs/facets", response_model=AuditFacets)
async def audit_facets(_: Admin, db: DB) -> AuditFacets:
    """Distinct actions and entity types, for the audit viewer's filters."""
    actions = (
        await db.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
    ).scalars()
    types = (
        await db.execute(select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type))
    ).scalars()
    return AuditFacets(actions=list(actions), entity_types=list(types))
