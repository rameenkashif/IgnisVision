"""Import every model so Base.metadata is complete (Alembic autogenerate, tests)."""

from app.models.analysis import (
    Alert,
    AnalysisJob,
    CaptureSession,
    MediaAsset,
    ThermalDetection,
    Victim,
    ZoneAssessment,
)
from app.models.identity import AuditLog, RefreshToken, Station, SystemSetting, User
from app.models.incidents import Floor, Incident, TeamAssignment, Zone
from app.models.sync_reports_training import (
    AttemptAnswer,
    IncidentReport,
    ScenarioItem,
    SyncBatch,
    TrainingAttempt,
    TrainingScenario,
)

__all__ = [
    "Alert",
    "AnalysisJob",
    "AttemptAnswer",
    "AuditLog",
    "CaptureSession",
    "Floor",
    "Incident",
    "IncidentReport",
    "MediaAsset",
    "RefreshToken",
    "ScenarioItem",
    "Station",
    "SyncBatch",
    "SystemSetting",
    "TeamAssignment",
    "ThermalDetection",
    "TrainingAttempt",
    "TrainingScenario",
    "User",
    "Victim",
    "Zone",
    "ZoneAssessment",
]
