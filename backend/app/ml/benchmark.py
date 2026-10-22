"""Benchmark the configured models against the SRS latency targets (MODEL_INTEGRATION §6).

    docker compose exec backend python -m app.ml.benchmark            # models from .env
    ML_BACKEND=real ... python -m app.ml.benchmark --images tests/ml/samples --runs 20

Reports per-model inference time and the zone-frame path (segmentation + damage in parallel,
then fusion) as the capture pipeline runs it.
"""

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from app.ml.registry import load_models
from app.services.settings import DEFAULTS
from app.services.video import read_image
from app.services.zone_fusion import fuse

ZONE_TARGET_MS = 6000  # frame → map, end to end (SRS §5.1.1)
THERMAL_TARGET_MS = 5000  # uploaded image → results


def _images(folder: str | None, size: tuple[int, int]) -> list[np.ndarray]:
    if folder:
        files = sorted(
            p for p in Path(folder).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
        )
        if files:
            return [read_image(str(p)) for p in files]
    rng = np.random.default_rng(0)
    h, w = size
    return [rng.integers(0, 255, (h, w, 3), dtype=np.uint8) for _ in range(3)]


def _time(fn, runs: int) -> list[float]:
    out = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def _row(name: str, ms: list[float], target: float | None = None) -> str:
    p95 = sorted(ms)[max(0, int(round(0.95 * (len(ms) - 1))))]
    verdict = "" if target is None else ("  PASS" if p95 <= target else "  FAIL")
    return f"{name:<34} mean {statistics.mean(ms):7.1f} ms   p95 {p95:7.1f} ms{verdict}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", help="folder of JPEG/PNG frames (default: synthetic 960×640)")
    ap.add_argument("--runs", type=int, default=10)
    args = ap.parse_args()

    models = load_models()
    imgs = _images(args.images, (640, 960))
    print(f"backend: {models.backend}  models: {models.versions()}  images: {len(imgs)}")
    for m in (models.pose, models.segmenter, models.damage):  # warm-up (lazy init, CUDA)
        m.predict(imgs[0])

    pick = iter(range(10**9))

    def img() -> np.ndarray:
        return imgs[next(pick) % len(imgs)]

    print(
        _row(
            "thermal pose (per image)",
            _time(lambda: models.pose.predict(img()), args.runs),
            THERMAL_TARGET_MS,
        )
    )
    print(_row("building segmentation", _time(lambda: models.segmenter.predict(img()), args.runs)))
    print(_row("damage segmentation", _time(lambda: models.damage.predict(img()), args.runs)))

    pool = ThreadPoolExecutor(2)

    def zone_frame() -> None:
        im = img()
        seg, dmg = pool.submit(models.segmenter.predict, im), pool.submit(models.damage.predict, im)
        fuse(seg.result(), dmg.result(), DEFAULTS["zone_fusion"])

    print(_row("zone frame (seg ∥ damage + fusion)", _time(zone_frame, args.runs), ZONE_TARGET_MS))
    print(
        "\nTargets are end to end; inference should stay well below them to leave room for "
        "upload, decoding and network time. Measure end to end with backend/loadtest/run.py."
    )


if __name__ == "__main__":
    main()
