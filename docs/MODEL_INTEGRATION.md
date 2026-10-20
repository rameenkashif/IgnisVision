# Model integration guide

The whole app runs on **mock models** behind a fixed contract. Integrating the trained models means implementing three adapter classes, placing the weights, and passing one acceptance test. **No code outside `backend/app/ml/` changes.**

## 1. What to implement

| Model | File to edit | Contract (`backend/app/ml/contracts.py`) | Weights env var |
|---|---|---|---|
| Thermal person detection + posture (YOLO-pose) | `app/ml/real/thermal_pose.py` → `UltralyticsThermalPose` | `ThermalPoseDetector.predict(image_rgb, temperature_c=None) -> list[PersonDetection]` | `THERMAL_POSE_WEIGHTS` |
| Building elements (SegFormer-B2) | `app/ml/real/segformer.py` → `SegFormerB2Segmenter` | `BuildingElementSegmenter.predict(image_rgb) -> ElementSegmentation` | `SEGFORMER_WEIGHTS` |
| Structural damage (YOLO-seg) | `app/ml/real/damage.py` → `YoloDamageSegmenter` | `StructuralDamageSegmenter.predict(image_rgb) -> list[DamageInstance]` | `DAMAGE_SEG_WEIGHTS` |

Each stub's docstring lists the exact steps (loading, preprocessing, output conversion). In short:

- **Input** is always an `H×W×3 uint8` **RGB** numpy array (Ultralytics expects BGR: flip with `image_rgb[..., ::-1]`).
- **Outputs are normalised** (0–1) for boxes, keypoints and polygons; masks and class maps are full input resolution (`H×W`).
- **Heavy imports go inside `load()`**, so the app still starts without `requirements-ml.txt` when `ML_BACKEND=mock`.
- Set `self.version` in `load()` to something that identifies the weights (e.g. `"yolov8s-pose-thermal@3f2a9c1e"`). It is stored on every assessment and detection, and shown in `/admin/status` and the reports.
- `predict()` is called from a thread pool (`ML_WORKERS`, default 4), possibly concurrently. Make it thread-safe or guard the model with a `threading.Lock`.

## 2. Class-mapping tables to fill in

- `SegFormerB2Segmenter.ADE20K_TO_ELEMENT`: model class id → one of `wall, floor, ceiling, door, window, column, stairs, other`. Pre-filled with the usual ADE20K ids. **Verify against `config.id2label`** of your fine-tuned model. Anything unmapped becomes `other`.
- `YoloDamageSegmenter.DAMAGE_CLASS_MAP`: trained class id → `crack, spalling, exposed_rebar, collapse, debris` (from your `data.yaml` `names`). Unmapped ids are skipped.
- `UltralyticsThermalPose.POSTURE_CLASS_MAP`: trained class id → `standing, sitting, lying, bending`, if posture is a class of the detector. If posture comes from a separate keypoint classifier, call it inside `predict()` instead.

## 3. Install, place weights, switch on

```bash
# 1. ML dependencies (CPU example; use the CUDA torch wheel for a GPU host)
pip install -r backend/requirements-ml.txt
#    In Docker: add `RUN pip install -r requirements-ml.txt` to backend/Dockerfile (or build a
#    separate ml image), and mount the weights read-only.

# 2. Weights (example layout)
mkdir -p models && cp yolo-pose-thermal.pt yolo-seg-damage.pt models/ && cp -r segformer-b2-ignis models/

# 3. .env
ML_BACKEND=real
ML_DEVICE=cpu            # or cuda
THERMAL_POSE_WEIGHTS=/models/yolo-pose-thermal.pt
SEGFORMER_WEIGHTS=/models/segformer-b2-ignis
DAMAGE_SEG_WEIGHTS=/models/yolo-seg-damage.pt
ML_ALLOW_MOCK_FALLBACK=false   # the app refuses to start if a real model fails to load
```

With Docker Compose, mount the folder into the backend (`volumes: - ./models:/models:ro`).

## 4. Acceptance test

```bash
cd backend
ML_BACKEND=real THERMAL_POSE_WEIGHTS=... SEGFORMER_WEIGHTS=... DAMAGE_SEG_WEIGHTS=... \
  pytest tests/ml/test_contract_conformance.py -v
```

It loads whatever the registry selects and checks types, shapes, value ranges, class names, and that a version is reported. Put a few real frames (JPEG/PNG: thermal and RGB building interiors) in `backend/tests/ml/samples/` to include them. **This test passing is the definition of "integrated".**

Then run the full suite (`pytest -q`) and the end-to-end demo (`docs/DEMO.md`, from Phase 9). Fusion, RPI, tracking, alerts and the UI need no changes.

## 5. Tuning after integration

The decision rules are application code with thresholds in **Admin → Settings** (stored in `system_settings`). They must be tuned on real footage with Rescue 1122:

- `zone_fusion`: minimum visible structure / confidence for "analysable", floor/door coverage and frame coverage for *blocked*, collapse confidence and crack/spalling area for *unsafe*, damage confidence for *caution*. Logic: `backend/app/services/zone_fusion.py` (HANDOFF §8.2). Tests: `tests/test_zone_fusion.py`.
- `rpi.*`: weights, posture scores and priority bands (Phase 5, HANDOFF §8.1).

## 6. Latency targets (SRS §5.1.1)

| Path | Target | How to measure |
|---|---|---|
| Uploaded thermal image → result | ≤ 5 s after upload | `analysis_jobs.finished_at - started_at`, and the Phase 5 job timing log |
| Zone frame → map update | ≤ 6 s | `latency_ms` in every `zone_result` message (capture screen shows it), and `backend/loadtest/` (Phase 9) |

On CPU, SegFormer-B2 at 512×512 plus YOLO-seg typically fit in well under a second per frame on a modern laptop; the pipeline runs both models in parallel and keeps only the latest frame per capture session, so slow inference lowers the effective frame rate instead of building a backlog. If needed, reduce `capture_fps` in settings or set `ML_DEVICE=cuda`.

## 7. After any model update

- Bump `self.version` (automatic if it includes the weights hash).
- Re-run the acceptance test.
- Recompute the trainer's stored reference outputs: **Admin → Scenarios → Recompute reference**, or `POST /api/v1/admin/scenarios/{id}/recompute-reference` (Phase 7). Items without a reference output are hidden from trainees.
