ROLES = ("admin", "incident_commander", "field_responder", "trainee", "training_staff")
LANGS = ("en", "ur")
DEVICE_KINDS = ("web", "mobile")

INCIDENT_STATUSES = ("draft", "dispatched", "active", "closed")
STRUCTURE_TYPES = ("commercial", "residential", "industrial", "other")
INCIDENT_TYPES = ("structural", "chemical", "electrical", "other")
INCIDENT_SOURCES = ("web", "mobile_sync")

ZONE_STATUSES = ("unclassified", "safe", "caution", "unsafe", "blocked")

MEDIA_KINDS = (
    "thermal_image",
    "thermal_video",
    "rgb_frame",
    "rgb_recording",
    "training_image",
    "training_video",
    "report_pdf",
    "floor_plan",
)
MEDIA_SOURCES = ("web_upload", "capture", "mobile_sync", "seed")
JOB_TYPES = ("thermal_pose", "zone_structure")
JOB_STATUSES = ("queued", "running", "done", "failed")

POSTURES = ("standing", "sitting", "lying", "bending")
RPI_BANDS = ("critical", "high", "medium", "low")
DETECTION_SOURCES = ("web_upload", "mobile_sync")
VICTIM_STATUSES = ("detected", "rescued", "false_positive")

ALERT_SEVERITIES = ("crit", "warn", "info")
ALERT_TYPES = (
    "zone_rapid_change",
    "zone_unsafe",
    "zone_blocked",
    "victim_critical",
    "analysis_failed",
    "camera_lost",
    "system",
)

SCENARIO_KINDS = ("zone", "posture", "mixed")
