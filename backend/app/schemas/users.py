import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["admin", "incident_commander", "field_responder", "trainee", "training_staff"]
Lang = Literal["en", "ur"]


class StationRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    username: str
    full_name: str
    role: Role
    preferred_language: Lang
    is_active: bool
    must_change_password: bool
    onboarding_completed: bool
    station: StationRef | None
    last_login_at: datetime | None
    created_at: datetime


class UserList(BaseModel):
    items: list[UserOut]
    total: int


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    preferred_language: Lang = "en"
    station_id: uuid.UUID | None = None
    # Omit to have the server generate a temporary password (returned once).
    password: str | None = None


class UserCreated(BaseModel):
    user: UserOut
    temporary_password: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    preferred_language: Lang | None = None
    station_id: uuid.UUID | None = None
    is_active: bool | None = None


class Confirm(BaseModel):
    confirm: bool


class ResetPassword(BaseModel):
    confirm: bool
    new_password: str | None = None


class PasswordReset(BaseModel):
    temporary_password: str
