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


class AuditList(BaseModel):
    items: list[AuditOut]
    total: int


@router.get("/audit-logs", response_model=AuditList)
async def audit_logs(
    _: Admin,
    db: DB,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
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
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = await db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset))
    items = [AuditOut.model_validate(r) for r in rows.scalars()]
    for i in items:
        i.ip = None if i.ip is None else str(i.ip)
    return AuditList(items=items, total=total)
