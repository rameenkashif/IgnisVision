import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, str_enum
from app.models.enums import DEVICE_KINDS, LANGS, ROLES


class Station(UUIDPk, Timestamps, Base):
    __tablename__ = "stations"
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120))
    region: Mapped[str] = mapped_column(String(120))


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    station_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stations.id"), index=True)
    username: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(str_enum(*ROLES, name="user_role"), index=True)
    preferred_language: Mapped[str] = mapped_column(
        str_enum(*LANGS, name="lang"), server_default="en"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default="false")
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    station: Mapped[Station | None] = relationship(lazy="joined")

    __table_args__ = (Index("uq_users_username_lower", func.lower(username), unique=True),)


class RefreshToken(UUIDPk, Base):
    """One row per issued refresh token. Rotation creates a new row in the same family
    (= one sign-in session); reuse of a rotated token revokes the whole family."""

    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Last user activity for the session (login / heartbeat); drives the 30-min idle rule.
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    device_kind: Mapped[str] = mapped_column(str_enum(*DEVICE_KINDS, name="device_kind"))


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(80))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
