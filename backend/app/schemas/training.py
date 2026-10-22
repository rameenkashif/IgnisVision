import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ZoneLabel = Literal["safe", "caution", "unsafe", "blocked"]
PostureLabel = Literal["standing", "sitting", "lying", "bending"]
Kind = Literal["zone", "posture", "mixed"]
Point = tuple[float, float]


def _unit(v: float) -> float:
    if not 0.0 <= v <= 1.0:
        raise ValueError("coordinates are normalised to 0–1")
    return v


class GTRegion(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    polygon: list[Point] = Field(min_length=3, max_length=64)
    status: ZoneLabel

    @field_validator("polygon")
    @classmethod
    def _norm(cls, v: list[Point]) -> list[Point]:
        return [(_unit(x), _unit(y)) for x, y in v]


class GTPerson(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    bbox: tuple[float, float, float, float]
    posture: PostureLabel

    @field_validator("bbox")
    @classmethod
    def _box(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = (_unit(c) for c in v)
        if x2 <= x1 or y2 <= y1:
            raise ValueError("bbox must be x1<x2, y1<y2")
        return (x1, y1, x2, y2)


class GroundTruth(BaseModel):
    """HANDOFF §9.6 ground-truth format; `frame_s` picks the labelled frame of a video."""

    type: Literal["zone", "posture"]
    regions: list[GTRegion] = Field(default_factory=list, max_length=64)
    people: list[GTPerson] = Field(default_factory=list, max_length=64)
    explanation_en: str = Field(default="", max_length=4000)
    explanation_ur: str = Field(default="", max_length=4000)
    frame_s: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ids(self) -> "GroundTruth":
        targets = self.regions if self.type == "zone" else self.people
        ids = [t.id for t in targets]
        if len(ids) != len(set(ids)):
            raise ValueError("target ids must be unique")
        return self


# ---- trainee views (ground truth withheld until submitted) ----


class PublicRegion(BaseModel):
    id: str
    polygon: list[Point]


class PublicPerson(BaseModel):
    id: str
    bbox: tuple[float, float, float, float]


class ItemPublic(BaseModel):
    id: uuid.UUID
    order: int
    type: Literal["zone", "posture"]
    media_kind: Literal["image", "video"]
    media_url: str | None
    width: int | None
    height: int | None
    frame_s: float | None
    regions: list[PublicRegion]
    people: list[PublicPerson]


class ScenarioSummary(BaseModel):
    id: uuid.UUID
    title_en: str
    title_ur: str
    description_en: str | None
    description_ur: str | None
    difficulty: int
    kind: Kind
    is_placeholder: bool
    item_count: int
    attempts: int = 0
    best_score: float | None = None


class ScenarioDetail(ScenarioSummary):
    items: list[ItemPublic]


class Answer(BaseModel):
    regions: dict[str, ZoneLabel] = Field(default_factory=dict)
    people: dict[str, PostureLabel] = Field(default_factory=dict)


class SubmitIn(BaseModel):
    answers: dict[uuid.UUID, Answer]


class AttemptSummary(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    scenario_title_en: str
    scenario_title_ur: str
    user_id: uuid.UUID
    user_name: str
    username: str
    started_at: datetime
    submitted_at: datetime | None
    score_pct: float | None
    model_agreement_pct: float | None


class TargetResult(BaseModel):
    id: str
    answer: str | None
    truth: str
    model: str | None
    credit: float
    correct: bool
    agrees_with_model: bool | None


class ItemResult(ItemPublic):
    """Result fields stay empty until the attempt is submitted."""

    ground_truth: dict[str, Any] | None = None
    reference_output: dict[str, Any] | None = None
    reference_model_version: str | None = None
    answer: Answer | None = None
    score: float | None = None
    targets: list[TargetResult] = []


class AttemptOut(AttemptSummary):
    scenario: ScenarioSummary
    items: list[ItemResult]
    llm_feedback: str | None
    llm_feedback_pending: bool
    correct_targets: int | None
    total_targets: int | None


# ---- admin ----


class ScenarioIn(BaseModel):
    title_en: str = Field(min_length=1, max_length=200)
    title_ur: str = Field(min_length=1, max_length=200)
    description_en: str | None = Field(default=None, max_length=4000)
    description_ur: str | None = Field(default=None, max_length=4000)
    difficulty: int = Field(default=1, ge=1, le=5)
    kind: Kind
    is_active: bool = True


class ScenarioPatch(BaseModel):
    title_en: str | None = Field(default=None, min_length=1, max_length=200)
    title_ur: str | None = Field(default=None, min_length=1, max_length=200)
    description_en: str | None = Field(default=None, max_length=4000)
    description_ur: str | None = Field(default=None, max_length=4000)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    kind: Kind | None = None
    is_active: bool | None = None


class AdminItem(BaseModel):
    id: uuid.UUID
    order: int
    media_id: uuid.UUID
    media_kind: Literal["image", "video"]
    media_url: str | None
    width: int | None
    height: int | None
    duration_s: float | None
    ground_truth: dict[str, Any]
    reference_output: dict[str, Any] | None
    reference_model_version: str | None
    usable: bool


class AdminScenario(ScenarioSummary):
    is_active: bool
    usable_count: int
    created_at: datetime


class AdminScenarioDetail(AdminScenario):
    items: list[AdminItem]


class ItemPatch(BaseModel):
    ground_truth: GroundTruth | None = None
    order: int | None = Field(default=None, ge=0)


class RecomputeOut(BaseModel):
    computed: int
    skipped: int
    failed: int
    model_version: str
