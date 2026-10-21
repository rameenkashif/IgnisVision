import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ReportFrame(BaseModel):
    kind: str
    zone: str | None
    status: str | None = None
    band: str | None = None
    posture: str | None = None
    at: str | None
    url: str | None


class ReportOut(BaseModel):
    incident_id: uuid.UUID
    generated_at: datetime
    generated_by: uuid.UUID | None
    narrative_en: str
    narrative_ur: str
    narrative_source: str
    stats: dict[str, Any]
    frames: list[ReportFrame]
