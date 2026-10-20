"""Deterministic mock models (the default, ML_BACKEND=mock).

Deterministic given (input image, scenario, clock) so tests are stable, and plausible in a live
demo: the damage level drifts over time instead of flickering frame to frame.

MOCK_SCENARIO:
  calm        mostly safe, occasionally caution, drifting once a minute
  escalating  safe → caution → unsafe over ~20 s from the start of a capture
  collapse    like escalating, ending in a blocked zone (collapse/debris on the floor)
A storyline restarts when a capture session starts (registry.capture_started) or after 30 s
without frames.
"""

import hashlib
import time
from collections.abc import Callable

import numpy as np

VERSION = "mock-1.0"


def image_seed(img: np.ndarray) -> int:
    """Stable seed from a coarse thumbnail, so near-identical frames share a seed."""
    small = img[:: max(1, img.shape[0] // 32), :: max(1, img.shape[1] // 32)]
    gray = small.mean(axis=2) if small.ndim == 3 else small
    q = (gray // 16).astype(np.uint8).tobytes()
    return int.from_bytes(hashlib.sha256(q).digest()[:8], "big")


class ScenarioClock:
    """Damage level 0–3 (none, minor, major, collapse) for the current moment."""

    IDLE_RESET_S = 30.0

    def __init__(self, scenario: str = "calm", clock: Callable[[], float] = time.monotonic):
        self.scenario = scenario
        self.clock = clock
        self._start: float | None = None
        self._last: float | None = None

    def restart(self) -> None:
        self._start = self._last = self.clock()

    def level(self) -> int:
        t = self.clock()
        if self._last is None or t - self._last > self.IDLE_RESET_S:
            self._start = t
        self._last = t
        elapsed = t - (self._start or t)
        if self.scenario == "escalating":
            return 0 if elapsed < 8 else 1 if elapsed < 16 else 2
        if self.scenario == "collapse":
            return 0 if elapsed < 6 else 1 if elapsed < 12 else 2 if elapsed < 18 else 3
        bucket = int(t // 60)
        r = int.from_bytes(hashlib.sha256(str(bucket).encode()).digest()[:2], "big") % 100
        return 0 if r < 70 else 1
