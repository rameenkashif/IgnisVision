from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.deps import DB, current_user_any_state, current_user_pending_password
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_params_public,
    hash_password,
    hash_token,
    needs_rehash,
    password_policy_violation,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.auth import (
    ChangePasswordIn,
    CredentialBundle,
    HeartbeatOut,
    LoginIn,
    MeUpdate,
    MobileLoginIn,
    MobileRefreshOut,
    MobileTokenOut,
    RefreshIn,
    TokenOut,
)
from app.schemas.users import UserOut
from app.services import auth_sessions as sessions

router = APIRouter(prefix="/auth", tags=["auth"])

PendingUser = Annotated[User, Depends(current_user_pending_password)]

# Verified against when the username doesn't exist, so response time doesn't reveal it.
_DUMMY_HASH = hash_password("timing-equaliser-0")


def _idle_s() -> int:
    return get_settings().idle_timeout_minutes * 60


def _set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.refresh_cookie_name,
        raw,
        max_age=s.refresh_token_days * 86400,
        path=s.refresh_cookie_path,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.refresh_cookie_name,
        path=s.refresh_cookie_path,
        httponly=True,
        secure=True,
        samesite="strict",
    )


async def _authenticate(db: DB, username: str, password: str) -> User:
    user = (
        await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    ).scalar_one_or_none()
    if user is None:
        verify_password(_DUMMY_HASH, password)
        raise AppError(401, "invalid_credentials")
    if not verify_password(user.password_hash, password):
        raise AppError(401, "invalid_credentials")
    if not user.is_active:
        raise AppError(403, "account_deactivated")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    return user


def _bundle(user: User) -> CredentialBundle:
    return CredentialBundle(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        preferred_language=user.preferred_language,
        password_hash=user.password_hash,
        hash_params=hash_params_public(),
        issued_at=datetime.now(UTC),
    )


def _refresh_token_from(request: Request, body: RefreshIn | None) -> str | None:
    if body and body.refresh_token:
        return body.refresh_token
    return request.cookies.get(get_settings().refresh_cookie_name)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response, db: DB) -> TokenOut:
    user = await _authenticate(db, body.username, body.password)
    raw, row = await sessions.issue(
        db, user, device_kind="web", user_agent=request.headers.get("user-agent")
    )
    access, ttl = create_access_token(user.id, user.role, row.family_id)
    await db.commit()
    await db.refresh(user)
    _set_refresh_cookie(response, raw)
    return TokenOut(
        access_token=access,
        expires_in=ttl,
        idle_timeout_s=_idle_s(),
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenOut | MobileRefreshOut)
async def refresh(
    request: Request, response: Response, db: DB, body: RefreshIn | None = None
) -> TokenOut | MobileRefreshOut:
    raw_in = _refresh_token_from(request, body)
    try:
        raw, row, user = await sessions.rotate(
            db, raw_in, user_agent=request.headers.get("user-agent")
        )
    except AppError as e:
        if e.status in (401, 410) and not (body and body.refresh_token):
            _clear_refresh_cookie(response)
            raise AppError(e.status, e.code, e.params) from None
        raise
    access, ttl = create_access_token(user.id, user.role, row.family_id)
    await db.commit()
    await db.refresh(user)
    common = dict(
        access_token=access,
        expires_in=ttl,
        idle_timeout_s=_idle_s(),
        user=UserOut.model_validate(user),
    )
    if row.device_kind == "mobile":
        return MobileRefreshOut(**common, refresh_token=raw, refresh_expires_at=row.expires_at)
    _set_refresh_cookie(response, raw)
    return TokenOut(**common)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, db: DB, body: RefreshIn | None = None
) -> Response:
    """Authenticated by the refresh token (cookie or body), so it works after the access token
    has expired. Ends the whole session family."""
    raw = _refresh_token_from(request, body)
    if not raw:
        raise AppError(401, "not_authenticated")
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    ).scalar_one_or_none()
    if row is None:
        raise AppError(401, "invalid_token")
    await sessions.revoke_family(db, row.family_id)
    await db.commit()
    _clear_refresh_cookie(response)
    response.status_code = 204
    return response


@router.post("/heartbeat", response_model=HeartbeatOut)
async def heartbeat(request: Request, user: PendingUser, db: DB) -> HeartbeatOut:
    """Marks the session as active (the frontend calls it on user interaction, and continuously
    on the live dashboard / capture screen of an active incident)."""
    await sessions.touch_activity(db, request.state.session_id)
    active = await sessions.in_active_incident(db, user.id)
    await db.commit()
    return HeartbeatOut(idle_timeout_s=_idle_s(), in_active_incident=active)


@router.get("/me", response_model=UserOut)
async def me(user: PendingUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: MeUpdate, user: PendingUser, db: DB) -> User:
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/change-password", status_code=204)
async def change_password(body: ChangePasswordIn, request: Request, user: PendingUser, db: DB):
    if not verify_password(user.password_hash, body.current_password):
        raise AppError(400, "current_password_incorrect")
    if (code := password_policy_violation(body.new_password)) is not None:
        raise AppError(422, code)
    if body.new_password == body.current_password:
        raise AppError(422, "password_unchanged")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    await sessions.revoke_all_for_user(db, user.id, except_family=request.state.session_id)
    await db.commit()
    return Response(status_code=204)


@router.post("/mobile/login", response_model=MobileTokenOut)
async def mobile_login(body: MobileLoginIn, request: Request, db: DB) -> MobileTokenOut:
    """Tokens + an offline credential bundle (contains the argon2 hash; see DECISIONS.md)."""
    user = await _authenticate(db, body.username, body.password)
    raw, row = await sessions.issue(
        db, user, device_kind="mobile", user_agent=request.headers.get("user-agent")
    )
    access, ttl = create_access_token(user.id, user.role, row.family_id)
    await db.commit()
    await db.refresh(user)
    return MobileTokenOut(
        access_token=access,
        expires_in=ttl,
        idle_timeout_s=_idle_s(),
        user=UserOut.model_validate(user),
        refresh_token=raw,
        refresh_expires_at=row.expires_at,
        credential_bundle=_bundle(user),
    )


@router.get("/mobile/refresh-bundle", response_model=CredentialBundle)
async def mobile_refresh_bundle(
    user: Annotated[User, Depends(current_user_any_state)],
) -> CredentialBundle:
    """410 Gone when the account is deactivated: the app must wipe its stored bundle."""
    if not user.is_active:
        raise AppError(410, "account_deactivated")
    return _bundle(user)
