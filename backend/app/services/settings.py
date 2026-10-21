"""System settings (HANDOFF §5 system_settings). Defaults are HANDOFF §8 values; all are
admin-editable and must be tuned with Rescue 1122 (see docs/DECISIONS.md Q6/Q7)."""

from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting

Unit = Field(ge=0.0, le=1.0)


class RpiWeights(BaseModel):
    w_p: float = Unit
    w_c: float = Unit
    w_r: float = Unit  # may be 0 (SRS §4.3 REQ-5)


class PostureScores(BaseModel):
    lying: float = Unit
    bending: float = Unit
    sitting: float = Unit
    standing: float = Unit


class RpiBands(BaseModel):
    critical: float = Unit
    high: float = Unit
    medium: float = Unit

    @model_validator(mode="after")
    def _ordered(self) -> "RpiBands":
        if not (self.critical > self.high > self.medium):
            raise ValueError("bands must satisfy critical > high > medium")
        return self


class ZoneFusion(BaseModel):
    min_structure_share: float = Unit
    min_confidence: float = Unit
    blocked_floor_door_share: float = Unit
    blocked_frame_share: float = Unit
    unsafe_collapse_conf: float = Unit
    unsafe_crack_spalling_share: float = Unit
    caution_damage_conf: float = Unit


class LlmFeatures(BaseModel):
    report_narrative: bool
    trainer_feedback: bool
    help_assistant: bool


class TrainerGrading(BaseModel):
    partial_credit_adjacent: bool
    adjacent_credit: float = Unit


SCHEMAS: dict[str, Any] = {
    "rpi.weights": RpiWeights,
    "rpi.posture_scores": PostureScores,
    "rpi.low_confidence_factor": float,
    "rpi.low_confidence_threshold": float,
    "rpi.bands": RpiBands,
    "zone_fusion": ZoneFusion,
    "stale_zone_seconds": int,
    "rapid_change_window_s": int,
    "analysis_failed_alert_interval_s": int,
    "evacuation_threshold_pct": int,
    "capture_fps": float,
    "retention_days": int | None,
    "llm.features": LlmFeatures,
    "trainer.grading": TrainerGrading,
}

DEFAULTS: dict[str, Any] = {
    "rpi.weights": {"w_p": 0.6, "w_c": 0.25, "w_r": 0.15},
    "rpi.posture_scores": {"lying": 1.0, "bending": 0.6, "sitting": 0.5, "standing": 0.2},
    "rpi.low_confidence_factor": 0.9,
    "rpi.low_confidence_threshold": 0.6,  # posture confidence below this → flagged
    "rpi.bands": {"critical": 0.75, "high": 0.55, "medium": 0.35},
    "zone_fusion": {
        "min_structure_share": 0.15,
        "min_confidence": 0.35,
        "blocked_floor_door_share": 0.25,
        "blocked_frame_share": 0.35,
        "unsafe_collapse_conf": 0.5,
        "unsafe_crack_spalling_share": 0.05,
        "caution_damage_conf": 0.4,
    },
    "stale_zone_seconds": 120,
    "rapid_change_window_s": 60,
    "analysis_failed_alert_interval_s": 60,
    "evacuation_threshold_pct": 40,
    "capture_fps": 1.0,
    "retention_days": None,  # off: no automatic deletion (Q14)
    "llm.features": {"report_narrative": False, "trainer_feedback": False, "help_assistant": False},
    "trainer.grading": {"partial_credit_adjacent": False, "adjacent_credit": 0.5},
}

# Readable by every signed-in user (dashboard colouring, capture rate, etc.).
PUBLIC_KEYS = {
    "rpi.bands",
    "stale_zone_seconds",
    "evacuation_threshold_pct",
    "capture_fps",
    "llm.features",
}

_SCALAR_BOUNDS: dict[str, tuple[float, float]] = {
    "rpi.low_confidence_factor": (0.0, 1.0),
    "rpi.low_confidence_threshold": (0.0, 1.0),
    "stale_zone_seconds": (10, 3600),
    "rapid_change_window_s": (5, 3600),
    "analysis_failed_alert_interval_s": (10, 3600),
    "evacuation_threshold_pct": (0, 100),
    "capture_fps": (0.2, 5.0),
    "retention_days": (1, 3650),
}


class SettingError(ValueError):
    def __init__(self, key: str, detail: str):
        super().__init__(f"{key}: {detail}")
        self.key = key
        self.detail = detail


def validate_setting(key: str, value: Any) -> Any:
    """Return the normalised value or raise SettingError."""
    from pydantic import TypeAdapter, ValidationError

    if key not in SCHEMAS:
        raise SettingError(key, "unknown_setting")
    try:
        normalised = TypeAdapter(SCHEMAS[key]).validate_python(value)
    except ValidationError as e:
        raise SettingError(key, e.errors()[0]["msg"]) from e
    if isinstance(normalised, BaseModel):
        return normalised.model_dump()
    if key in _SCALAR_BOUNDS and normalised is not None:
        lo, hi = _SCALAR_BOUNDS[key]
        if not lo <= normalised <= hi:
            raise SettingError(key, f"must be between {lo} and {hi}")
    return normalised


async def load_all(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(SystemSetting))).scalars().all()
    values = dict(DEFAULTS)
    values.update({r.key: r.value for r in rows if r.key in SCHEMAS})
    return values


async def ensure_defaults(db: AsyncSession) -> int:
    existing = set((await db.execute(select(SystemSetting.key))).scalars().all())
    missing = [k for k in DEFAULTS if k not in existing]
    for k in missing:
        db.add(SystemSetting(key=k, value=DEFAULTS[k]))
    return len(missing)
