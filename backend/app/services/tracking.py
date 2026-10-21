"""Person tracking across sampled video frames (HANDOFF §8.3, SRS REQ-7, UC-01 AF3).

Greedy IoU matching with a centroid-distance fallback. A track is *confirmed* once seen in
≥ 2 consecutive samples; short misses (≤ max_misses samples) don't end it."""

from dataclasses import dataclass, field


def iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _centre(b: tuple[float, ...]) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


@dataclass
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    hits: int = 1
    streak: int = 1  # consecutive samples seen
    misses: int = 0
    confirmed: bool = False
    observations: list[int] = field(default_factory=list)  # indices into the caller's detections


class Tracker:
    def __init__(
        self,
        iou_threshold: float = 0.3,
        max_centre_dist: float = 0.12,
        max_misses: int = 2,
        confirm_after: int = 2,
    ):
        self.iou_threshold = iou_threshold
        self.max_centre_dist = max_centre_dist
        self.max_misses = max_misses
        self.confirm_after = confirm_after
        self.tracks: list[Track] = []
        self._next = 1

    def update(
        self, boxes: list[tuple[float, float, float, float]], obs_ids: list[int]
    ) -> list[int]:
        """Feed one sampled frame. Returns the track id assigned to each box (same order)."""
        live = [t for t in self.tracks if t.misses <= self.max_misses]
        pairs = []
        for ti, t in enumerate(live):
            for bi, b in enumerate(boxes):
                score = iou(t.bbox, b)
                if score < self.iou_threshold:
                    (tx, ty), (bx, by) = _centre(t.bbox), _centre(b)
                    dist = ((tx - bx) ** 2 + (ty - by) ** 2) ** 0.5
                    if dist > self.max_centre_dist:
                        continue
                    score = 0.01 * (1 - dist)  # weaker than any IoU match
                pairs.append((score, ti, bi))
        pairs.sort(reverse=True)
        used_t: set[int] = set()
        assigned: dict[int, int] = {}
        for _, ti, bi in pairs:
            if ti in used_t or bi in assigned:
                continue
            used_t.add(ti)
            t = live[ti]
            t.bbox = boxes[bi]
            t.hits += 1
            t.streak = t.streak + 1 if t.misses == 0 else 1
            t.misses = 0
            t.observations.append(obs_ids[bi])
            if t.streak >= self.confirm_after:
                t.confirmed = True
            assigned[bi] = t.id
        for ti, t in enumerate(live):
            if ti not in used_t:
                t.misses += 1
        for bi, b in enumerate(boxes):
            if bi not in assigned:
                t = Track(self._next, b, observations=[obs_ids[bi]])
                t.confirmed = self.confirm_after <= 1
                self._next += 1
                self.tracks.append(t)
                assigned[bi] = t.id
        return [assigned[i] for i in range(len(boxes))]

    def confirmed(self) -> list[Track]:
        return [t for t in self.tracks if t.confirmed]
