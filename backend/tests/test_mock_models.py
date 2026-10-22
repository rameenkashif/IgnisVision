import numpy as np

from app.ml.mock import ScenarioClock
from app.ml.mock.models import MockBuildingSegmenter, MockDamageSegmenter, MockThermalPose
from app.services.settings import DEFAULTS
from app.services.zone_fusion import fuse


def scene(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_deterministic_for_same_input():
    seg = MockBuildingSegmenter()
    a, b = seg.predict(scene(7)), seg.predict(scene(7))
    assert np.array_equal(a.class_map, b.class_map) and a.confidence == b.confidence
    pose = MockThermalPose()
    assert pose.predict(scene(7)) == pose.predict(scene(7))


def test_escalating_storyline_safe_caution_unsafe():
    clock = FakeClock()
    dmg = MockDamageSegmenter(ScenarioClock("escalating", clock))
    seg = MockBuildingSegmenter()
    statuses = []
    for _ in range(25):
        img = scene()
        statuses.append(fuse(seg.predict(img), dmg.predict(img), DEFAULTS["zone_fusion"]).status)
        clock.t += 1
    assert statuses[0] == "safe" and statuses[10] == "caution" and statuses[-1] == "unsafe"


def test_collapse_storyline_ends_blocked_and_restarts_after_idle():
    clock = FakeClock()
    dmg = MockDamageSegmenter(ScenarioClock("collapse", clock))
    seg = MockBuildingSegmenter()
    last = None
    for _ in range(20):
        img = scene()
        last = fuse(seg.predict(img), dmg.predict(img), DEFAULTS["zone_fusion"]).status
        clock.t += 1
    assert last == "blocked"
    clock.t += 60  # idle → new capture restarts the story
    img = scene()
    assert fuse(seg.predict(img), dmg.predict(img), DEFAULTS["zone_fusion"]).status == "safe"


def test_obscured_frame_is_not_analysable():
    grey = np.full((240, 320, 3), 128, dtype=np.uint8)
    r = fuse(
        MockBuildingSegmenter().predict(grey),
        MockDamageSegmenter().predict(grey),
        DEFAULTS["zone_fusion"],
    )
    assert r.analysable is False


def test_storyline_restarts_on_new_capture():
    clock = FakeClock()
    sc = ScenarioClock("escalating", clock)
    sc.level()
    clock.t += 20
    assert sc.level() == 2
    sc.restart()
    assert sc.level() == 0
