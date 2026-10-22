import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum
from app.models.enums import (
    INCIDENT_SOURCES,
    INCIDENT_STATUSES,
    INCIDENT_TYPES,
    STRUCTURE_TYPES,
    ZONE_STATUSES,
)

incident_code_seq = Sequence("incident_code_seq", metadata=Base.metadata)


class Incident(UUIDPk, Timestamps, Base):
    __tablename__ = "incidents"
    station_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stations.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # e.g. IV-2026-0412
    address: Mapped[str | None] = mapped_column(String(400))
    city: Mapped[str | None] = mapped_column(String(120))
    structure_type: Mapped[str] = mapped_column(
        str_enum(*STRUCTURE_TYPES, name="structure_type"), server_default="other"
    )
    incident_type: Mapped[str] = mapped_column(
        str_enum(*INCIDENT_TYPES, name="incident_type"), server_default="other"
    )
    reported_by: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        str_enum(*INCIDENT_STATUSES, name="incident_status"), server_default="draft", index=True
    )
    commander_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    summary_text: Mapped[str | None] = mapped_column(Text)
    floor_plan_media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", use_alter=True)
    )
    source: Mapped[str] = mapped_column(
        str_enum(*INCIDENT_SOURCES, name="incident_source"), server_default="web"
    )
    client_uuid: Mapped[str | None] = mapped_column(String(64), unique=True)  # mobile dedupe
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Floor(UUIDPk, Timestamps, Base):
    __tablename__ = "floors"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("incident_id", "number"),)


class Zone(UUIDPk, Timestamps, Base):
    __tablename__ = "zones"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    floor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("floors.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(32))  # e.g. F1-Z3
    label: Mapped[str | None] = mapped_column(String(120))
    grid_row: Mapped[int] = mapped_column(Integer)
    grid_col: Mapped[int] = mapped_column(Integer)
    polygon: Mapped[Any | None] = mapped_column(JSONB)
    current_status: Mapped[str] = mapped_column(
        str_enum(*ZONE_STATUSES, name="zone_status"), server_default="unclassified"
    )
    current_assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zone_assessments.id", use_alter=True)
    )
    status_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("incident_id", "code"),)


class TeamAssignment(UUIDPk, Timestamps, Base):
    """History is kept: reassigning sets unassigned_at instead of overwriting."""

    __tablename__ = "team_assignments"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    device_label: Mapped[str | None] = mapped_column(String(120))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
