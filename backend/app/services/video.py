"""Frame access for thermal uploads (OpenCV, used only from the ML thread pool)."""

import io

import cv2
import numpy as np
from PIL import Image

SAMPLE_FPS = 2.0  # SRS REQ-7
MAX_WIDTH = 1280


def _fit(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    if w <= MAX_WIDTH:
        return rgb
    return cv2.resize(rgb, (MAX_WIDTH, int(h * MAX_WIDTH / w)), interpolation=cv2.INTER_AREA)


def read_image(path: str) -> np.ndarray:
    with Image.open(path) as im:
        return _fit(np.asarray(im.convert("RGB")))


class VideoSampler:
    """Iterates a video at ~2 samples per second without decoding every frame to RGB."""

    def __init__(self, path: str, sample_fps: float = SAMPLE_FPS):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError("unreadable_video")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        if not (1.0 <= self.fps <= 240.0):
            self.fps = 25.0
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.step = max(1, round(self.fps / sample_fps))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.index = 0

    @property
    def duration_s(self) -> float | None:
        return self.frame_count / self.fps if self.frame_count else None

    @property
    def expected_samples(self) -> int:
        return max(1, (self.frame_count + self.step - 1) // self.step) if self.frame_count else 1

    def next(self) -> tuple[int, int, np.ndarray] | None:
        """(frame_index, timestamp_ms, rgb) of the next sample, or None at the end."""
        while True:
            idx = self.index
            if idx % self.step == 0:
                ok, bgr = self.cap.read()
                self.index += 1
                if not ok:
                    return None
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                return idx, int(1000 * idx / self.fps), _fit(rgb)
            if not self.cap.grab():
                return None
            self.index += 1

    def close(self) -> None:
        self.cap.release()


def frame_jpeg(rgb: np.ndarray, width: int = 960) -> bytes:
    img = Image.fromarray(rgb)
    if img.width > width:
        img = img.resize((width, int(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=78)
    return buf.getvalue()


def frames_prefix(storage_key: str) -> str:
    """Sampled frames of a video are stored next to it: <key>.frames/<index>_<ms>.jpg"""
    return f"{storage_key}.frames"


def thumbnail_jpeg(path: str, is_video: bool, width: int = 320) -> bytes:
    if is_video:
        cap = cv2.VideoCapture(path)
        ok, bgr = cap.read()
        cap.release()
        if not ok:
            raise ValueError("unreadable_video")
        img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    else:
        img = Image.open(path).convert("RGB")
    img.thumbnail((width, width * 2))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=75)
    return buf.getvalue()


def probe_image(path: str) -> tuple[int, int]:
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        return im.width, im.height
