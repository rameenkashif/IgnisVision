import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.users import Lang, Role, UserOut


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class MobileLoginIn(LoginIn):
    device_id: str | None = Field(default=None, max_length=120)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    idle_timeout_s: int
    user: UserOut


class RefreshIn(BaseModel):
    refresh_token: str | None = None  # mobile; web uses the httpOnly cookie


class CredentialBundle(BaseModel):
    """Stored by the Flutter app in secure storage for offline sign-in (SRS UC-08 AF1)."""

    user_id: uuid.UUID
    username: str
    full_name: str
    role: Role
    preferred_language: Lang
    password_hash: str
    hash_params: dict
    issued_at: datetime


class MobileTokenOut(TokenOut):
    refresh_token: str
    refresh_expires_at: datetime
    credential_bundle: CredentialBundle


class MobileRefreshOut(TokenOut):
    refresh_token: str
    refresh_expires_at: datetime


class MeUpdate(BaseModel):
    preferred_language: Lang | None = None
    onboarding_completed: bool | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class HeartbeatOut(BaseModel):
    ok: bool = True
    idle_timeout_s: int
    in_active_incident: bool
