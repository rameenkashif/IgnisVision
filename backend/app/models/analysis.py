import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum
from app.models.enums import (
    ALERT_SEVERITIES,
    ALERT_TYPES,
    DETECTION_SOURCES,
    JOB_STATUSES,
    JOB_TYPES,
    MEDIA_KINDS,
    MEDIA_SOURCES,
    POSTURES,
    RPI_BANDS,
    VICTIM_STATUSES,
    ZONE_STATUSES,
)


class MediaAsset(UUIDPk, Timestamps, Base):
    __tablename__ = "media_assets"
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(str_enum(*MEDIA_KINDS, name="media_kind"), index=True)
    storage_key: Mapped[str] = mapped_column(String(400), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_s: Mapped[float | None] = mapped_column(Float)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(str_enum(*MEDIA_SOURCES, name="media_source"))


class CaptureSession(UUIDPk, Timestamps, Base):
    __tablename__ = "capture_sessions"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    frames_received: Mapped[int] = mapped_column(Integer, server_default="0")
    frames_analysed: Mapped[int] = mapped_column(Integer, server_default="0")
    recording_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id"))


class AnalysisJob(UUIDPk, Timestamps, Base):
    __tablename__ = "analysis_jobs"
    media_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    job_type: Mapped[str] = mapped_column(str_enum(*JOB_TYPES, name="job_type"))
    status: Mapped[str] = mapped_column(
        str_enum(*JOB_STATUSES, name="job_status"), server_default="queued", index=True
    )
    progress: Mapped[float] = mapped_column(Float, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(120))
    model_version: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ZoneAssessment(UUIDPk, Base):
    """Insert-only zone risk history (SRS UC-05 postcondition)."""

    __tablename__ = "zone_assessments"
    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"), index=True
    )
    capture_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="SET NULL"), index=True
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id"))
    status: Mapped[str] = mapped_column(str_enum(*ZONE_STATUSES, name="zone_status"))
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    analysable: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list[Any]] = mapped_column(JSONB, server_default="[]")
    segmentation_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    damage_instances: Mapped[list[Any] | None] = mapped_column(JSONB)
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ThermalDetection(UUIDPk, Base):
    __tablename__ = "thermal_detections"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"), index=True
    )
    media_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    analysis_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="SET NULL")
    )
    frame_index: Mapped[int | None] = mapped_column(Integer)
    timestamp_ms: Mapped[int | None] = mapped_column(BigInteger)
    track_id: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[list[float]] = mapped_column(JSONB)
    keypoints: Mapped[list[Any] | None] = mapped_column(JSONB)
    posture: Mapped[str] = mapped_column(str_enum(*POSTURES, name="posture"))
    posture_confidence: Mapped[float] = mapped_column(Float)
    low_confidence: Mapped[bool] = mapped_column(Boolean, server_default="false")
    detection_confidence: Mapped[float] = mapped_column(Float)
    env_risk: Mapped[float | None] = mapped_column(Float)
    rpi_score: Mapped[float] = mapped_column(Float)
    rpi_band: Mapped[str] = mapped_column(str_enum(*RPI_BANDS, name="rpi_band"))
    source: Mapped[str] = mapped_column(str_enum(*DETECTION_SOURCES, name="detection_source"))
    client_detection_uuid: Mapped[str | None] = mapped_column(String(64), unique=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # e.g. {"mobile_rpi": 0.86}
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Victim(UUIDPk, Timestamps, Base):
    """Aggregated per tracked person; gives the dashboard a stable ranked list."""

    __tablename__ = "victims"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    track_key: Mapped[str] = mapped_column(String(120))
    best_detection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("thermal_detections.id", ondelete="SET NULL")
    )
    latest_posture: Mapped[str] = mapped_column(str_enum(*POSTURES, name="posture"))
    latest_rpi_score: Mapped[float] = mapped_column(Float, index=True)
    latest_rpi_band: Mapped[str] = mapped_column(str_enum(*RPI_BANDS, name="rpi_band"))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        str_enum(*VICTIM_STATUSES, name="victim_status"), server_default="detected"
    )
    source: Mapped[str] = mapped_column(str_enum(*DETECTION_SOURCES, name="detection_source"))


class Alert(UUIDPk, Base):
    __tablename__ = "alerts"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    severity: Mapped[str] = mapped_column(str_enum(*ALERT_SEVERITIES, name="alert_severity"))
    type: Mapped[str] = mapped_column(str_enum(*ALERT_TYPES, name="alert_type"))
    message_key: Mapped[str] = mapped_column(String(120))
    message_params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
