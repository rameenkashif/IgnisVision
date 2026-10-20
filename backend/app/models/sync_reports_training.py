import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPk, str_enum
from app.models.enums import LANGS, SCENARIO_KINDS


class SyncBatch(UUIDPk, Base):
    __tablename__ = "sync_batches"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(120))
    app_version: Mapped[str | None] = mapped_column(String(40))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    incident_count: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)


class IncidentReport(UUIDPk, Timestamps, Base):
    __tablename__ = "incident_reports"
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), unique=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    pdf_media_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_assets.id"))
    language: Mapped[str] = mapped_column(str_enum(*LANGS, name="lang"), server_default="en")
    narrative: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class TrainingScenario(UUIDPk, Timestamps, Base):
    __tablename__ = "training_scenarios"
    title_en: Mapped[str] = mapped_column(String(200))
    title_ur: Mapped[str] = mapped_column(String(200))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_ur: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(Integer, server_default="1")
    kind: Mapped[str] = mapped_column(str_enum(*SCENARIO_KINDS, name="scenario_kind"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    is_placeholder: Mapped[bool] = mapped_column(Boolean, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ScenarioItem(UUIDPk, Timestamps, Base):
    __tablename__ = "scenario_items"
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_scenarios.id", ondelete="CASCADE"), index=True
    )
    order: Mapped[int] = mapped_column(Integer)
    media_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id"))
    ground_truth: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reference_output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reference_model_version: Mapped[str | None] = mapped_column(String(200))


class TrainingAttempt(UUIDPk, Timestamps, Base):
    __tablename__ = "training_attempts"
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_scenarios.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score_pct: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    llm_feedback: Mapped[str | None] = mapped_column(Text)


class AttemptAnswer(UUIDPk, Timestamps, Base):
    __tablename__ = "attempt_answers"
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_attempts.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenario_items.id", ondelete="CASCADE"), index=True
    )
    answer: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    per_target_results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
