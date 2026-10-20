import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.engine import get_db
from app.models import User

DB = Annotated[AsyncSession, Depends(get_db)]


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError(401, "not_authenticated")
    return token


async def _load_user(request: Request, db: AsyncSession) -> tuple[User, dict]:
    try:
        claims = decode_access_token(_bearer(request))
    except jwt.ExpiredSignatureError as e:
        raise AppError(401, "token_expired") from e
    except jwt.InvalidTokenError as e:
        raise AppError(401, "invalid_token") from e
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise AppError(401, "invalid_token")
    request.state.session_id = uuid.UUID(claims["sid"])
    return user, claims


async def current_user_any_state(request: Request, db: DB) -> User:
    """Authenticated user even if deactivated — only for endpoints that must report that state."""
    user, _ = await _load_user(request, db)
    return user


async def current_user_pending_password(request: Request, db: DB) -> User:
    """Active user; allowed while must_change_password is set (me / change-password / logout)."""
    user, _ = await _load_user(request, db)
    if not user.is_active:
        raise AppError(401, "account_deactivated")
    return user


async def current_user(user: Annotated[User, Depends(current_user_pending_password)]) -> User:
    if user.must_change_password:
        raise AppError(403, "password_change_required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: str):
    """Backend RBAC guard (HANDOFF §6). The frontend only hides what it can't use."""

    async def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden")
        return user

    return _guard


async def bearer_user(request: Request, db: AsyncSession) -> User:
    """For endpoints that authenticate conditionally (e.g. signed media URLs)."""
    user, _ = await _load_user(request, db)
    if not user.is_active:
        raise AppError(401, "account_deactivated")
    if user.must_change_password:
        raise AppError(403, "password_change_required")
    return user
