import numpy as np
import pytest

from app.ml.contracts import DamageInstance, ElementSegmentation
from app.services.settings import DEFAULTS
from app.services.zone_fusion import fuse

CFG = DEFAULTS["zone_fusion"]
H = W = 100
CLASSES = {0: "wall", 1: "floor", 2: "ceiling", 3: "door", 7: "other"}


def room(conf: float = 0.85) -> ElementSegmentation:
    """Ceiling rows 0-19, wall 20-69 (door at cols 60-74 from row 40), floor 70-99."""
    cm = np.zeros((H, W), dtype=np.uint8)
    cm[:20] = 2
    cm[70:] = 1
    cm[40:70, 60:75] = 3
    return ElementSegmentation(cm, dict(CLASSES), conf)


def rect(cls, conf, y1, y2, x1, x2) -> DamageInstance:
    m = np.zeros((H, W), dtype=bool)
    m[y1:y2, x1:x2] = True
    return DamageInstance(cls, conf, m, [(x1 / W, y1 / H), (x2 / W, y2 / H), (x1 / W, y2 / H)])


def test_no_damage_is_safe():
    r = fuse(room(), [], CFG)
    assert (r.status, r.analysable) == ("safe", True)
    assert r.reasons[0]["key"] == "reasons.no_damage"
    assert r.segmentation_summary["wall"] > 0.3


def test_low_confidence_damage_ignored():
    assert fuse(room(), [rect("crack", 0.3, 25, 30, 10, 20)], CFG).status == "safe"


def test_credible_minor_damage_is_caution():
    r = fuse(room(), [rect("crack", 0.45, 25, 30, 10, 20)], CFG)  # 0.5 % of frame
    assert r.status == "caution"
    assert r.damage[0]["element"] == "wall" and r.damage[0]["area_pct"] == 0.5


def test_surface_damage_over_5pct_of_structure_is_unsafe():
    # crack 20x20 + spalling 10x20 on the wall = 600 px = 6 % of the frame (threshold 5 %)
    r = fuse(
        room(), [rect("crack", 0.7, 25, 45, 10, 30), rect("spalling", 0.6, 25, 35, 30, 50)], CFG
    )
    assert r.status == "unsafe"
    assert any(x["key"] == "reasons.surface_damage" for x in r.reasons)


def test_surface_damage_under_5pct_is_only_caution():
    r = fuse(
        room(), [rect("crack", 0.7, 25, 35, 10, 30), rect("spalling", 0.6, 25, 30, 30, 40)], CFG
    )
    assert r.status == "caution"  # 250 px = 2.5 %


def test_surface_damage_on_floor_does_not_count_as_structural():
    # 6 % crack area entirely on the floor → caution, not unsafe
    r = fuse(room(), [rect("crack", 0.7, 70, 76, 0, 100)], CFG)
    assert r.status == "caution"


def test_credible_collapse_is_unsafe():
    r = fuse(room(), [rect("collapse", 0.55, 25, 30, 10, 15)], CFG)
    assert r.status == "unsafe" and r.reasons[0]["key"] == "reasons.collapse_detected"


def test_debris_over_quarter_of_floor_and_door_is_blocked():
    # floor 3000 px + door 450 px = 3450; debris covers rows 70-99 cols 0-35 = 1050 px → 30 %
    r = fuse(room(), [rect("debris", 0.6, 70, 100, 0, 35)], CFG)
    assert r.status == "blocked" and r.risk_score >= 0.9
    assert r.reasons[0]["key"] == "reasons.passage_blocked"


def test_obstruction_over_35pct_of_frame_is_blocked():
    r = fuse(room(), [rect("collapse", 0.45, 0, 60, 0, 60)], CFG)  # 36 % of the frame, on walls
    assert r.status == "blocked" and r.reasons[0]["key"] == "reasons.frame_obstructed"


@pytest.mark.parametrize(
    "seg",
    [
        room(conf=0.2),  # model unsure
        ElementSegmentation(
            np.full((H, W), 7, np.uint8), dict(CLASSES), 0.9
        ),  # smoke: no structure
    ],
)
def test_not_analysable_never_claims_safe(seg):
    r = fuse(seg, [], CFG)
    assert r.analysable is False and r.status == "unclassified"
    assert r.reasons[0]["key"] == "reasons.not_analysable"


def test_thresholds_come_from_settings():
    strict = {**CFG, "caution_damage_conf": 0.9}
    assert fuse(room(), [rect("crack", 0.45, 25, 30, 10, 20)], strict).status == "safe"
