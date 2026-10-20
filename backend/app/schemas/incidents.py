import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

StructureType = Literal["commercial", "residential", "industrial", "other"]
IncidentType = Literal["structural", "chemical", "electrical", "other"]
IncidentStatus = Literal["draft", "dispatched", "active", "closed"]
ZoneStatus = Literal["unclassified", "safe", "caution", "unsafe", "blocked"]
Severity = Literal["crit", "warn", "info"]


class UserRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    username: str


class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    number: int
    label: str


class ZoneOut(BaseModel):
    id: uuid.UUID
    floor_id: uuid.UUID
    floor_number: int
    code: str
    label: str | None
    grid_row: int
    grid_col: int
    # Effective status: stale or never-analysed zones are "unclassified", never "safe".
    status: ZoneStatus
    stored_status: ZoneStatus
    stale: bool
    status_updated_at: datetime | None
    risk_score: float | None
    confidence: float | None
    assessment_id: uuid.UUID | None
    assignees: list[UserRef]
    victim_count: int


class AssignmentOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    zone_id: uuid.UUID | None
    zone_code: str | None
    user: UserRef
    device_label: str | None
    assigned_at: datetime
    unassigned_at: datetime | None
    assigned_by: uuid.UUID | None


class Kpis(BaseModel):
    zones_total: int
    zones_by_status: dict[ZoneStatus, int]
    classified: int
    building_status: ZoneStatus
    evac_ok_pct: float | None  # safe + caution share of *classified* zones
    unclassified_pct: float
    evacuation_threshold_pct: int
    below_threshold: bool
    victims_detected: int
    response_units: int
    ai_confidence: float | None
    stale_zone_seconds: int


class IncidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    address: str | None
    city: str | None
    structure_type: StructureType
    incident_type: IncidentType
    reported_by: str | None
    status: IncidentStatus
    source: str
    opened_at: datetime
    activated_at: datetime | None
    closed_at: datetime | None


class IncidentList(BaseModel):
    items: list[IncidentSummary]
    total: int


class IncidentDetail(IncidentSummary):
    commander: UserRef | None
    summary_text: str | None
    floors: list[FloorOut]
    zones: list[ZoneOut]
    assignments: list[AssignmentOut]
    kpis: Kpis


class AssignmentIn(BaseModel):
    user_id: uuid.UUID
    zone_code: str | None = Field(default=None, max_length=32)
    device_label: str | None = Field(default=None, max_length=120)


class IncidentCreate(BaseModel):
    """Matches the prototype's dispatch modal: one transaction creates everything."""

    address: str = Field(min_length=1, max_length=400)
    city: str | None = Field(default=None, max_length=120)
    structure_type: StructureType = "other"
    incident_type: IncidentType = "other"
    reported_by: str | None = Field(default=None, max_length=200)
    floors: int = Field(ge=1, le=50)
    zones_per_floor: int = Field(ge=1, le=20)
    zone_labels: dict[str, str] = Field(default_factory=dict)  # {"F1-Z2": "Lobby"}
    assignments: list[AssignmentIn] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def _labels_known(self) -> "IncidentCreate":
        valid = {
            f"F{f}-Z{z}"
            for f in range(1, self.floors + 1)
            for z in range(1, self.zones_per_floor + 1)
        }
        used = {a.zone_code for a in self.assignments if a.zone_code}
        unknown = (set(self.zone_labels) | used) - valid
        if unknown:
            raise ValueError(f"unknown zone codes: {sorted(unknown)}")
        for label in self.zone_labels.values():
            if len(label) > 120:
                raise ValueError("zone label too long")
        users = [a.user_id for a in self.assignments]
        if len(users) != len(set(users)):
            raise ValueError("a responder can only be assigned once")
        return self


class IncidentUpdate(BaseModel):
    address: str | None = Field(default=None, min_length=1, max_length=400)
    city: str | None = Field(default=None, max_length=120)
    structure_type: StructureType | None = None
    incident_type: IncidentType | None = None
    reported_by: str | None = Field(default=None, max_length=200)
    summary_text: str | None = Field(default=None, max_length=10000)


class ZoneUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=120)


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    zone_id: uuid.UUID
    status: ZoneStatus
    risk_score: float
    confidence: float
    analysable: bool
    reasons: list
    created_at: datetime


class AssignmentCreate(BaseModel):
    user_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    device_label: str | None = Field(default=None, max_length=120)


class MyAssignment(AssignmentOut):
    incident_code: str
    incident_status: IncidentStatus


class ResponderOut(BaseModel):
    id: uuid.UUID
    full_name: str
    username: str
    active_incident_code: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_id: uuid.UUID
    zone_id: uuid.UUID | None
    severity: Severity
    type: str
    message_key: str
    message_params: dict
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    created_at: datetime


class AlertList(BaseModel):
    items: list[AlertOut]
    total: int
