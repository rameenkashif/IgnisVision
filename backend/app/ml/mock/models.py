from collections.abc import Callable

import numpy as np

from app.ml.contracts import (
    POSTURES,
    DamageInstance,
    ElementSegmentation,
    PersonDetection,
)
from app.ml.mock import VERSION, ScenarioClock, image_seed

_CLASSES = {0: "wall", 1: "floor", 2: "ceiling", 3: "door", 4: "window", 5: "column",
            6: "stairs", 7: "other"}  # fmt: skip


def _is_obscured(img: np.ndarray) -> bool:
    """Heavy smoke / covered lens: almost no contrast → nothing recognisable."""
    return float(img.std()) < 8.0


class MockBuildingSegmenter:
    name = "mock-segformer"
    version = VERSION

    def load(self) -> None:
        pass

    def predict(self, image_rgb: np.ndarray) -> ElementSegmentation:
        h, w = image_rgb.shape[:2]
        cm = np.full((h, w), 7, dtype=np.uint8)
        if _is_obscured(image_rgb):
            cm[int(h * 0.9) :, :] = 1  # a sliver of floor; far below the structure threshold
            return ElementSegmentation(cm, dict(_CLASSES), confidence=0.25)
        rng = np.random.default_rng(image_seed(image_rgb))
        ceil, floor = int(h * rng.uniform(0.18, 0.26)), int(h * rng.uniform(0.68, 0.75))
        cm[:ceil] = 2
        cm[ceil:floor] = 0
        cm[floor:] = 1
        dx = int(w * rng.uniform(0.55, 0.7))
        cm[int(h * 0.35) : floor, dx : dx + int(w * 0.14)] = 3  # door
        cm[ceil:floor, : int(w * 0.06)] = 5  # column
        return ElementSegmentation(cm, dict(_CLASSES), confidence=float(rng.uniform(0.78, 0.9)))


def _rect_instance(cls, conf, h, w, x1, y1, x2, y2) -> DamageInstance:
    m = np.zeros((h, w), dtype=bool)
    m[int(y1 * h) : int(y2 * h), int(x1 * w) : int(x2 * w)] = True
    return DamageInstance(cls, conf, m, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)])


class MockDamageSegmenter:
    name = "mock-yolo-seg"
    version = VERSION

    def __init__(
        self,
        clock: ScenarioClock | None = None,
        level_fn: Callable[[np.ndarray], int] | None = None,
    ):
        self.clock = clock or ScenarioClock()
        self.level_fn = level_fn  # set for trainer references: damage level read from the image

    def load(self) -> None:
        pass

    def predict(self, image_rgb: np.ndarray) -> list[DamageInstance]:
        h, w = image_rgb.shape[:2]
        if _is_obscured(image_rgb):
            return []
        level = self.level_fn(image_rgb) if self.level_fn else self.clock.level()
        rng = np.random.default_rng(image_seed(image_rgb) ^ level)
        # Kept on the wall band (left of the mock door at x ≥ 0.55, above the floor at y ≥ 0.68).
        x, y = rng.uniform(0.08, 0.25), rng.uniform(0.3, 0.38)
        if level == 0:
            return []
        if level == 1:  # hairline crack: ~1.5 % of the frame → caution
            return [_rect_instance("crack", 0.48, h, w, x, y, x + 0.1, y + 0.15)]
        if level == 2:  # crack + spalling on the wall: ≥ 7.5 % → unsafe
            return [
                _rect_instance("crack", 0.74, h, w, x, y, x + 0.25, y + 0.3),
                _rect_instance("spalling", 0.66, h, w, x + 0.22, y, x + 0.34, y + 0.15),
            ]
        return [  # collapse/debris over the floor and doorway → blocked
            _rect_instance("debris", 0.81, h, w, 0.0, 0.62, 1.0, 1.0),
            _rect_instance("collapse", 0.77, h, w, 0.5, 0.3, 0.9, 0.75),
        ]


def painted_damage_level(img: np.ndarray) -> int:
    """Damage level from the share of very dark pixels (cracks, spalling, debris painted in dark
    tones). Lets the trainer's mock reference output follow what an image shows instead of the
    live-capture storyline clock; real models never use this."""
    luma = img[..., :3] @ np.array([0.299, 0.587, 0.114]) if img.ndim == 3 else img
    dark = float((luma < 50).mean())
    return 0 if dark < 0.008 else 1 if dark < 0.05 else 2 if dark < 0.18 else 3


class MockThermalPose:
    name = "mock-yolo-pose"
    version = VERSION

    def load(self) -> None:
        pass

    def predict(
        self, image_rgb: np.ndarray, temperature_c: np.ndarray | None = None
    ) -> list[PersonDetection]:
        if _is_obscured(image_rgb):
            return []
        rng = np.random.default_rng(image_seed(image_rgb))
        people: list[PersonDetection] = []
        for i in range(int(rng.integers(0, 4))):
            posture = POSTURES[int(rng.integers(0, 4))]
            cx = 0.15 + 0.3 * i + rng.uniform(-0.05, 0.05)
            bw, bh = (0.28, 0.14) if posture == "lying" else (0.12, 0.36)
            cy = 0.7 if posture == "lying" else 0.55
            x1, y1 = max(0.0, cx - bw / 2), max(0.0, cy - bh / 2)
            x2, y2 = min(1.0, cx + bw / 2), min(1.0, cy + bh / 2)
            kps = [
                (float(x1 + (x2 - x1) * rng.uniform()), float(y1 + (y2 - y1) * rng.uniform()),
                 float(rng.uniform(0.5, 0.95)))
                for _ in range(17)
            ]  # fmt: skip
            people.append(
                PersonDetection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    detection_confidence=float(rng.uniform(0.55, 0.95)),
                    posture=posture,
                    posture_confidence=float(rng.uniform(0.45, 0.95)),
                    keypoints=kps,
                )
            )
        return people
