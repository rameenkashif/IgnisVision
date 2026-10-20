from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request

from app.core.deps import DB, CurrentUser, require_roles
from app.core.errors import AppError
from app.models import SystemSetting, User
from app.services import audit
from app.services import settings as svc

router = APIRouter(tags=["settings"])
Admin = Annotated[User, Depends(require_roles("admin"))]


@router.get("/settings")
async def public_settings(_: CurrentUser, db: DB) -> dict[str, Any]:
    values = await svc.load_all(db)
    return {k: v for k, v in values.items() if k in svc.PUBLIC_KEYS}


@router.get("/admin/settings")
async def all_settings(_: Admin, db: DB) -> dict[str, Any]:
    return await svc.load_all(db)


@router.patch("/admin/settings")
async def update_settings(
    request: Request,
    admin: Admin,
    db: DB,
    changes: Annotated[dict[str, Any], Body(examples=[{"evacuation_threshold_pct": 45}])],
) -> dict[str, Any]:
    if not changes:
        raise AppError(422, "no_changes")
    normalised: dict[str, Any] = {}
    for key, value in changes.items():
        try:
            normalised[key] = svc.validate_setting(key, value)
        except svc.SettingError as e:
            raise AppError(422, "invalid_setting", {"key": e.key, "detail": e.detail}) from None
    current = await svc.load_all(db)
    for key, value in normalised.items():
        row = await db.get(SystemSetting, key)
        if row is None:
            db.add(SystemSetting(key=key, value=value, updated_by=admin.id))
        else:
            row.value = value
            row.updated_by = admin.id
    await audit.record(
        db,
        actor_id=admin.id,
        action="settings.update",
        entity_type="system_settings",
        before={k: current.get(k) for k in normalised},
        after=normalised,
        request=request,
    )
    await db.commit()
    return await svc.load_all(db)
