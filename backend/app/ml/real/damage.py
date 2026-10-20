import numpy as np

from app.ml.contracts import DamageInstance


class YoloDamageSegmenter:
    """YOLO-seg trained on structural damage (Φ-Net / SDNET2018-based) → damage instances.

    TO IMPLEMENT
    - Weights: Ultralytics segmentation `.pt` at env DAMAGE_SEG_WEIGHTS.
    - load(): `YOLO(path)`; move to ML_DEVICE; warm up.
    - Preprocessing: `imgsz` = training size (typically 640); input RGB → BGR for Ultralytics.
    - Output conversion, per instance:
        cls = DAMAGE_CLASS_MAP[class_id]  (skip ids not in the map)
        confidence = boxes.conf[i]
        mask = masks.data[i] resized to the input H×W (nearest), > 0.5 → bool
        polygon = masks.xyn[i] (normalised outline) → list of (x, y) tuples
    Acceptance: backend/tests/ml/test_contract_conformance.py with ML_BACKEND=real.
    """

    name = "yolo-seg-damage"
    version = "unloaded"

    # Trained class id → contract DamageClass. FILL IN from the training data.yaml `names`.
    DAMAGE_CLASS_MAP: dict[int, str] = {
        # 0: "crack", 1: "spalling", 2: "exposed_rebar", 3: "collapse", 4: "debris",
    }

    def load(self) -> None:
        raise NotImplementedError("Damage segmenter not integrated — see MODEL_INTEGRATION.md")

    def predict(self, image_rgb: np.ndarray) -> list[DamageInstance]:
        raise NotImplementedError
