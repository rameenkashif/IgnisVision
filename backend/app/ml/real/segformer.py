import numpy as np

from app.ml.contracts import ElementSegmentation


class SegFormerB2Segmenter:
    """SegFormer-B2 (ADE20K-based, fine-tuned) → per-pixel building element map.

    TO IMPLEMENT
    - Weights: Hugging Face folder (config.json + model.safetensors + preprocessor_config.json)
      at env SEGFORMER_WEIGHTS, or an exported ONNX.
    - load(): `SegformerForSemanticSegmentation.from_pretrained(path)` +
      `SegformerImageProcessor.from_pretrained(path)`; `.eval()`; move to ML_DEVICE; warm up.
    - Preprocessing: the processor resizes to 512×512 and normalises with ImageNet
      mean/std (0.485, 0.456, 0.406 / 0.229, 0.224, 0.225). Input is HxWx3 uint8 RGB.
    - Output conversion: logits (1, C, H/4, W/4) → upsample to the input H×W (bilinear) →
      softmax → argmax = model class ids; confidence = mean of the per-pixel max probability.
      Map model class ids → contract ElementClass with ADE20K_TO_ELEMENT below (anything
      unmapped → "other"), and return ElementSegmentation(class_map uint8, classes, confidence)
      where `classes` maps the uint8 values you emit to ElementClass names.
    Acceptance: backend/tests/ml/test_contract_conformance.py with ML_BACKEND=real.
    """

    name = "segformer-b2"
    version = "unloaded"

    # ADE20K (or fine-tuned) class id → ElementClass. FILL IN / VERIFY against the model's
    # config.id2label. Common ADE20K ids shown for reference:
    ADE20K_TO_ELEMENT: dict[int, str] = {
        0: "wall",  # wall
        3: "floor",  # floor
        5: "ceiling",  # ceiling
        8: "window",  # windowpane
        14: "door",  # door
        42: "column",  # column, pillar
        53: "stairs",  # stairs
        59: "stairs",  # stairway
        # everything else → "other"
    }

    def load(self) -> None:
        raise NotImplementedError("SegFormer not integrated — see MODEL_INTEGRATION.md")

    def predict(self, image_rgb: np.ndarray) -> ElementSegmentation:
        raise NotImplementedError
