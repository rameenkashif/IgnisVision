"""THE MODEL SEAM (HANDOFF §9). Everything outside app/ml/ depends only on this module;
nothing outside app/ml/ may import torch, ultralytics or transformers (SRS §5.4.3)."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np

Posture = Literal["standing", "sitting", "lying", "bending"]
POSTURES: tuple[Posture, ...] = ("standing", "sitting", "lying", "bending")


@dataclass
class PersonDetection:
    bbox: tuple[float, float, float, float]  # normalised x1,y1,x2,y2 in [0,1]
    detection_confidence: float
    posture: Posture
    posture_confidence: float
    keypoints: list[tuple[float, float, float]] | None = None  # 17 COCO kpts (x,y,conf), normalised


class ThermalPoseDetector(Protocol):
    name: str
    version: str

    def load(self) -> None: ...

    def predict(
        self, image_rgb: np.ndarray, temperature_c: np.ndarray | None = None
    ) -> list[PersonDetection]:
        """image_rgb: HxWx3 uint8 (colourised thermal); temperature_c: HxW float32 if available."""
        ...


ElementClass = Literal["wall", "floor", "ceiling", "door", "window", "column", "stairs", "other"]
ELEMENT_CLASSES: tuple[ElementClass, ...] = (
    "wall",
    "floor",
    "ceiling",
    "door",
    "window",
    "column",
    "stairs",
    "other",
)


@dataclass
class ElementSegmentation:
    class_map: np.ndarray  # HxW uint8 index into `classes`
    classes: dict[int, ElementClass]
    confidence: float  # mean max-softmax or similar, 0–1

    def share(self) -> dict[ElementClass, float]:
        """Pixel fraction per element class (classes with no pixels are omitted)."""
        total = self.class_map.size
        if total == 0:
            return {}
        idx, counts = np.unique(self.class_map, return_counts=True)
        out: dict[ElementClass, float] = {}
        for i, c in zip(idx.tolist(), counts.tolist(), strict=True):
            name = self.classes.get(int(i), "other")
            out[name] = out.get(name, 0.0) + c / total
        return out

    def mask(self, *names: ElementClass) -> np.ndarray:
        ids = [i for i, n in self.classes.items() if n in names]
        return np.isin(self.class_map, ids)


class BuildingElementSegmenter(Protocol):  # SegFormer-B2 (ADE20K-based)
    name: str
    version: str

    def load(self) -> None: ...

    def predict(self, image_rgb: np.ndarray) -> ElementSegmentation: ...


DamageClass = Literal["crack", "spalling", "exposed_rebar", "collapse", "debris"]
DAMAGE_CLASSES: tuple[DamageClass, ...] = (
    "crack",
    "spalling",
    "exposed_rebar",
    "collapse",
    "debris",
)


@dataclass
class DamageInstance:
    cls: DamageClass
    confidence: float
    mask: np.ndarray  # HxW bool
    polygon: list[tuple[float, float]] = field(default_factory=list)  # normalised, for the UI


class StructuralDamageSegmenter(Protocol):  # YOLO-seg (Φ-Net / SDNET2018-based)
    name: str
    version: str

    def load(self) -> None: ...

    def predict(self, image_rgb: np.ndarray) -> list[DamageInstance]: ...
