"""Rescue Priority Index (HANDOFF §8.1, SRS §4.3).

    RPI = w_p·P(posture) + w_c·C(detection confidence) + w_r·R(environmental risk)

All weights, posture scores and bands come from system_settings (admin-editable, to be tuned
with Rescue 1122). When R is unavailable the RPI uses posture and confidence only, with their
weights renormalised so scores stay on the same 0–1 scale (SRS UC-03 AF2).
"""

from dataclasses import dataclass
from typing import Any

ENV_RISK_BY_ZONE = {"unsafe": 1.0, "blocked": 1.0, "caution": 0.5, "safe": 0.0}


@dataclass(frozen=True)
class RpiResult:
    score: float
    band: str  # critical | high | medium | low
    low_confidence: bool
    env_risk_used: bool


def env_risk_from_zone(effective_status: str | None) -> float | None:
    """Web uploads: environmental risk from the tagged zone's *current* status.
    Unclassified or stale zones → unavailable (None), never 0."""
    return ENV_RISK_BY_ZONE.get(effective_status or "")


def band_for(score: float, bands: dict[str, float]) -> str:
    if score >= bands["critical"]:
        return "critical"
    if score >= bands["high"]:
        return "high"
    if score >= bands["medium"]:
        return "medium"
    return "low"


def compute(
    *,
    posture: str,
    posture_confidence: float,
    detection_confidence: float,
    env_risk: float | None,
    settings: dict[str, Any],
    low_confidence: bool | None = None,
) -> RpiResult:
    w = settings["rpi.weights"]
    p_score = float(settings["rpi.posture_scores"][posture])
    if low_confidence is None:
        low_confidence = posture_confidence < float(settings["rpi.low_confidence_threshold"])
    if low_confidence:
        p_score *= float(settings["rpi.low_confidence_factor"])  # still ranked, and flagged
    c = min(1.0, max(0.0, float(detection_confidence)))

    if env_risk is None or w["w_r"] == 0:
        denom = w["w_p"] + w["w_c"]
        score = (w["w_p"] * p_score + w["w_c"] * c) / denom if denom else 0.0
        used = False
    else:
        r = min(1.0, max(0.0, float(env_risk)))
        score = w["w_p"] * p_score + w["w_c"] * c + w["w_r"] * r
        used = True
    score = round(min(1.0, max(0.0, score)), 4)
    return RpiResult(score, band_for(score, settings["rpi.bands"]), low_confidence, used)
