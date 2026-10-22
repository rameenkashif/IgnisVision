import numpy as np

from app.ml.contracts import PersonDetection


class UltralyticsThermalPose:
    """YOLO-pose on colourised thermal frames → person boxes, 17 keypoints and posture.

    TO IMPLEMENT
    - Weights: Ultralytics `.pt` (or exported `.onnx`) at env THERMAL_POSE_WEIGHTS.
    - load(): `from ultralytics import YOLO; self.model = YOLO(path)`; move to ML_DEVICE;
      run one warm-up inference on a 640×640 zero image. Set `self.version` to something that
      identifies the weights (e.g. file name + sha256[:8]).
    - Preprocessing: Ultralytics handles letterboxing; pass `imgsz=640` (or the training size),
      `conf=0.25`, `verbose=False`. Input is HxWx3 uint8 RGB — Ultralytics expects BGR numpy, so
      flip channels (`image_rgb[..., ::-1]`).
    - Output conversion, per detection:
        bbox = boxes.xyxyn[i] (already normalised) → tuple of 4 floats
        detection_confidence = boxes.conf[i]
        keypoints = keypoints.xyn[i] + keypoints.conf[i] → 17 × (x, y, conf), normalised
    - Posture: either the trained model has posture classes (then map its class ids with
      POSTURE_CLASS_MAP below and use the class confidence as posture_confidence), or posture
      comes from a keypoint classifier — call it here and return its label + probability.
    - temperature_c: optional HxW °C array from the mobile/radiometric source; use it only if
      the model was trained with it.
    - Must be thread-safe for concurrent predict() calls, or guard the model with a lock.
    Acceptance: backend/tests/ml/test_contract_conformance.py with ML_BACKEND=real.
    """

    name = "yolo-pose-thermal"
    version = "unloaded"

    # Trained class id → contract posture. FILL IN from the training config.
    POSTURE_CLASS_MAP: dict[int, str] = {
        # 0: "standing", 1: "sitting", 2: "lying", 3: "bending",
    }

    def load(self) -> None:
        raise NotImplementedError("Thermal pose model not integrated — see MODEL_INTEGRATION.md")

    def predict(
        self, image_rgb: np.ndarray, temperature_c: np.ndarray | None = None
    ) -> list[PersonDetection]:
        raise NotImplementedError
