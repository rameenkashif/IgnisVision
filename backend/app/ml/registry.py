"""Picks mock or real models from the environment (HANDOFF §9.2).

ML_BACKEND=mock|real, ML_DEVICE=cpu|cuda, THERMAL_POSE_WEIGHTS, SEGFORMER_WEIGHTS,
DAMAGE_SEG_WEIGHTS, MOCK_SCENARIO=calm|escalating|collapse, ML_ALLOW_MOCK_FALLBACK=false.
If `real` fails to load the app refuses to start, unless the fallback is explicitly allowed.
"""

import logging
import os
from dataclasses import dataclass

from app.ml.contracts import (
    BuildingElementSegmenter,
    StructuralDamageSegmenter,
    ThermalPoseDetector,
)

log = logging.getLogger(__name__)


@dataclass
class Models:
    backend: str
    pose: ThermalPoseDetector
    segmenter: BuildingElementSegmenter
    damage: StructuralDamageSegmenter
    fallback_reason: str | None = None

    def versions(self) -> dict[str, str]:
        return {m.name: m.version for m in (self.pose, self.segmenter, self.damage)}


_models: Models | None = None


def _mock() -> Models:
    from app.ml.mock import ScenarioClock
    from app.ml.mock.models import MockBuildingSegmenter, MockDamageSegmenter, MockThermalPose

    clock = ScenarioClock(os.environ.get("MOCK_SCENARIO", "calm"))
    return Models("mock", MockThermalPose(), MockBuildingSegmenter(), MockDamageSegmenter(clock))


def _real() -> Models:
    from app.ml.real.damage import YoloDamageSegmenter
    from app.ml.real.segformer import SegFormerB2Segmenter
    from app.ml.real.thermal_pose import UltralyticsThermalPose

    return Models("real", UltralyticsThermalPose(), SegFormerB2Segmenter(), YoloDamageSegmenter())


def load_models() -> Models:
    global _models
    backend = os.environ.get("ML_BACKEND", "mock")
    models = _real() if backend == "real" else _mock()
    try:
        for m in (models.pose, models.segmenter, models.damage):
            m.load()
    except Exception as e:
        if os.environ.get("ML_ALLOW_MOCK_FALLBACK", "false").lower() != "true":
            raise RuntimeError(
                f"ML_BACKEND={backend} failed to load ({e!r}). Fix the weights/config, or set "
                "ML_ALLOW_MOCK_FALLBACK=true to start with mock models."
            ) from e
        log.error("Real models failed to load (%r); falling back to mocks", e)
        models = _mock()
        models.fallback_reason = repr(e)
    log.info("ML backend: %s %s", models.backend, models.versions())
    _models = models
    return models


def get_models() -> Models:
    return _models or load_models()


def set_models(models: Models | None) -> None:
    """Test hook."""
    global _models
    _models = models


def capture_started() -> None:
    """Hook for the capture stream: lets mock storylines start fresh for each session.
    Real models ignore it."""
    models = get_models()
    clock = getattr(models.damage, "clock", None)
    if models.backend == "mock" and hasattr(clock, "restart"):
        clock.restart()
