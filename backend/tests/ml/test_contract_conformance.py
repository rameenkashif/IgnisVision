"""ACCEPTANCE TEST FOR MODEL INTEGRATION (HANDOFF §9.5).

Runs whichever implementation the registry loads (ML_BACKEND=mock|real) against sample images
and checks output types, shapes and ranges against app/ml/contracts.py.

    ML_BACKEND=real THERMAL_POSE_WEIGHTS=... SEGFORMER_WEIGHTS=... DAMAGE_SEG_WEIGHTS=... \\
        pytest tests/ml/test_contract_conformance.py -v

Drop real sample images (JPEG/PNG) into tests/ml/samples/ to include them.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.ml.contracts import (
    DAMAGE_CLASSES,
    ELEMENT_CLASSES,
    POSTURES,
    DamageInstance,
    ElementSegmentation,
    PersonDetection,
)
from app.ml.registry import load_models, set_models

SAMPLES = Path(__file__).parent / "samples"


def _images() -> list[tuple[str, np.ndarray]]:
    rng = np.random.default_rng(0)
    imgs = [
        ("noise_640x480", rng.integers(0, 255, (480, 640, 3), dtype=np.uint8)),
        ("noise_portrait_720x1280", rng.integers(0, 255, (1280, 720, 3), dtype=np.uint8)),
        ("grey_smoke", np.full((360, 640, 3), 128, dtype=np.uint8)),
        ("tiny_64x48", rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)),
    ]
    for p in sorted(SAMPLES.glob("*")) if SAMPLES.exists() else []:
        if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            imgs.append((p.name, np.asarray(Image.open(p).convert("RGB"))))
    return imgs


IMAGES = _images()


@pytest.fixture(scope="module")
def models():
    m = load_models()
    yield m
    set_models(None)


def test_models_report_name_and_version(models):
    for m in (models.pose, models.segmenter, models.damage):
        assert isinstance(m.name, str) and m.name
        assert isinstance(m.version, str) and m.version and m.version != "unloaded"


@pytest.mark.parametrize(("name", "img"), IMAGES, ids=[n for n, _ in IMAGES])
def test_segmenter_contract(models, name, img):
    seg = models.segmenter.predict(img)
    assert isinstance(seg, ElementSegmentation)
    assert seg.class_map.shape == img.shape[:2], "class_map must match the input H×W"
    assert seg.class_map.dtype == np.uint8
    assert set(np.unique(seg.class_map).tolist()) <= set(seg.classes), "unmapped class ids"
    assert set(seg.classes.values()) <= set(ELEMENT_CLASSES)
    assert 0.0 <= seg.confidence <= 1.0
    assert abs(sum(seg.share().values()) - 1.0) < 1e-6


@pytest.mark.parametrize(("name", "img"), IMAGES, ids=[n for n, _ in IMAGES])
def test_damage_contract(models, name, img):
    out = models.damage.predict(img)
    assert isinstance(out, list)
    for d in out:
        assert isinstance(d, DamageInstance)
        assert d.cls in DAMAGE_CLASSES
        assert 0.0 <= d.confidence <= 1.0
        assert d.mask.shape == img.shape[:2] and d.mask.dtype == bool
        assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y in d.polygon)


@pytest.mark.parametrize(("name", "img"), IMAGES, ids=[n for n, _ in IMAGES])
def test_pose_contract(models, name, img):
    out = models.pose.predict(img)
    assert isinstance(out, list)
    for p in out:
        assert isinstance(p, PersonDetection)
        x1, y1, x2, y2 = p.bbox
        assert 0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0
        assert 0.0 <= p.detection_confidence <= 1.0
        assert p.posture in POSTURES and 0.0 <= p.posture_confidence <= 1.0
        if p.keypoints is not None:
            assert len(p.keypoints) == 17
            assert all(0 <= x <= 1 and 0 <= y <= 1 and 0 <= c <= 1 for x, y, c in p.keypoints)


def test_pose_accepts_temperature(models):
    img = IMAGES[0][1]
    temp = np.full(img.shape[:2], 22.0, dtype=np.float32)
    assert isinstance(models.pose.predict(img, temp), list)
