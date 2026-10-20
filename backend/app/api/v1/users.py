import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.core.security import hash_password, password_policy_violation
from app.models import Station, User
from app.schemas.users import (
    Confirm,
    PasswordReset,
    ResetPassword,
    Role,
    UserCreate,
    UserCreated,
    UserList,
    UserOut,
    UserUpdate,
)
from app.services import audit
from app.services import auth_sessions as sessions
from app.services.users_util import temporary_password

router = APIRouter(prefix="/users", tags=["users"])
Admin = Annotated[User, Depends(require_roles("admin"))]

_SNAPSHOT = (
    "username",
    "full_name",
    "role",
    "preferred_language",
    "station_id",
    "is_active",
    "must_change_password",
)


def snapshot(user: User) -> dict:
    """Audit view of a user — never includes the password hash."""
    return {f: (str(v) if isinstance(v := getattr(user, f), uuid.UUID) else v) for f in _SNAPSHOT}


async def _get(db: DB, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(404, "user_not_found")
    return user


async def _check_station(db: DB, station_id: uuid.UUID | None) -> None:
    if station_id is not None and await db.get(Station, station_id) is None:
        raise AppError(422, "station_not_found")


@router.get("", response_model=UserList)
async def list_users(
    _: Admin,
    db: DB,
    role: Role | None = None,
    is_active: bool | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserList:
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(func.lower(User.username).like(like), func.lower(User.full_name).like(like))
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.order_by(User.username).limit(limit).offset(offset))).scalars()
    return UserList(items=[UserOut.model_validate(u) for u in rows.unique()], total=total)


@router.post("", response_model=UserCreated, status_code=201)
async def create_user(body: UserCreate, request: Request, admin: Admin, db: DB) -> UserCreated:
    generated = body.password is None
    password = body.password or temporary_password()
    if (code := password_policy_violation(password)) is not None:
        raise AppError(422, code)
    await _check_station(db, body.station_id)
    user = User(
        username=body.username,
        full_name=body.full_name,
        role=body.role,
        preferred_language=body.preferred_language,
        station_id=body.station_id or admin.station_id,
        password_hash=hash_password(password),
        must_change_password=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "username_taken") from None
    await audit.record(
        db,
        actor_id=admin.id,
        action="user.create",
        entity_type="user",
        entity_id=user.id,
        after=snapshot(user),
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return UserCreated(
        user=UserOut.model_validate(user), temporary_password=password if generated else None
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, _: Admin, db: DB) -> User:
    return await _get(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, request: Request, admin: Admin, db: DB
) -> User:
    user = await _get(db, user_id)
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        changes.get("role") not in (None, "admin") or changes.get("is_active") is False
    ):
        raise AppError(409, "cannot_modify_self")
    if "station_id" in changes:
        await _check_station(db, changes["station_id"])
    before = snapshot(user)
    for field, value in changes.items():
        if value is not None or field == "station_id":
            setattr(user, field, value)
    if changes.get("is_active") is False or "role" in changes:
        await sessions.revoke_all_for_user(db, user.id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="user.update",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=snapshot(user),
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: uuid.UUID, body: Confirm, request: Request, admin: Admin, db: DB
) -> User:
    if not body.confirm:
        raise AppError(400, "confirmation_required")
    user = await _get(db, user_id)
    if user.id == admin.id:
        raise AppError(409, "cannot_modify_self")
    before = snapshot(user)
    user.is_active = False
    await sessions.revoke_all_for_user(db, user.id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="user.deactivate",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=snapshot(user),
        request=request,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=PasswordReset)
async def reset_password(
    user_id: uuid.UUID, body: ResetPassword, request: Request, admin: Admin, db: DB
) -> PasswordReset:
    """Admin-only reset (SRS UC-08 AF2); the user must change it at next sign-in."""
    if not body.confirm:
        raise AppError(400, "confirmation_required")
    user = await _get(db, user_id)
    password = body.new_password or temporary_password()
    if (code := password_policy_violation(password)) is not None:
        raise AppError(422, code)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    await sessions.revoke_all_for_user(db, user.id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="user.reset_password",
        entity_type="user",
        entity_id=user.id,
        after={"must_change_password": True},
        request=request,
    )
    await db.commit()
    return PasswordReset(temporary_password=password)
