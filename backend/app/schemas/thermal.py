import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Posture = Literal["standing", "sitting", "lying", "bending"]
Band = Literal["critical", "high", "medium", "low"]


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    media_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    frame_index: int | None
    timestamp_ms: int | None
    track_id: int | None
    bbox: list[float]
    keypoints: list | None
    posture: Posture
    posture_confidence: float
    low_confidence: bool
    detection_confidence: float
    env_risk: float | None
    rpi_score: float
    rpi_band: Band
    source: str
    detected_at: datetime
    frame_url: str | None = None  # sampled video frame (signed); None for still images


class SampleFrame(BaseModel):
    frame_index: int
    timestamp_ms: int
    url: str


class VictimOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    zone_id: uuid.UUID | None
    zone_code: str | None
    track_key: str
    posture: Posture
    posture_confidence: float | None
    low_confidence: bool
    detection_confidence: float | None
    rpi_score: float  # highest RPI observed for this person (ranking key)
    rpi_band: Band
    env_risk: float | None
    status: Literal["detected", "rescued", "false_positive"]
    source: Literal["web_upload", "mobile_sync"]
    first_seen_at: datetime
    last_seen_at: datetime
    best_detection_id: uuid.UUID | None
    media_id: uuid.UUID | None
    media_url: str | None
    frame_url: str | None = None
    timestamp_ms: int | None
    bbox: list[float] | None


class VictimUpdate(BaseModel):
    status: Literal["detected", "rescued", "false_positive"]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    media_id: uuid.UUID
    job_type: str
    status: Literal["queued", "running", "done", "failed"]
    progress: float
    error: str | None
    model_name: str | None
    model_version: str | None
    started_at: datetime | None
    finished_at: datetime | None


class UploadAccepted(BaseModel):
    media_id: uuid.UUID
    job_id: uuid.UUID


class ThermalUploadOut(BaseModel):
    media_id: uuid.UUID
    kind: Literal["thermal_image", "thermal_video"]
    source: str
    zone_id: uuid.UUID | None
    zone_code: str | None
    created_at: datetime
    url: str
    thumbnail_url: str
    duration_s: float | None
    width: int | None
    height: int | None
    job: JobOut | None
    detections: int
    people: int


# ---- mobile sync (HANDOFF §7.4) ----


class SyncDetection(BaseModel):
    client_detection_uuid: str = Field(min_length=1, max_length=64)
    captured_at: datetime
    mode: Literal["live", "still"] = "live"
    track_id: int | None = None
    bbox: list[float] = Field(min_length=4, max_length=4)
    keypoints: list[list[float]] | None = None
    posture: Posture
    posture_confidence: float = Field(ge=0, le=1)
    low_confidence: bool = False
    detection_confidence: float = Field(ge=0, le=1)
    env_risk: float | None = Field(default=None, ge=0, le=1)
    rpi_score: float | None = Field(default=None, ge=0, le=1)
    rpi_band: Band | None = None
    frame_ref: str | None = Field(default=None, max_length=200)


class SyncIncident(BaseModel):
    client_uuid: str = Field(min_length=1, max_length=64)
    started_at: datetime
    ended_at: datetime | None = None
    label: str | None = Field(default=None, max_length=400)
    linked_incident_id: uuid.UUID | None = None
    detections: list[SyncDetection] = Field(default_factory=list, max_length=5000)


class SyncPayload(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)
    incidents: list[SyncIncident] = Field(min_length=1, max_length=50)


class SyncResult(BaseModel):
    client_uuid: str
    status: Literal["created", "duplicate", "error"]
    incident_id: uuid.UUID | None = None
    error: str | None = None


class SyncResponse(BaseModel):
    results: list[SyncResult]
