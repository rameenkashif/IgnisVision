"""Overlay PNG for the capture screen and dashboard: element colours + damage outlines."""

import io

import numpy as np
from PIL import Image, ImageDraw

from app.ml.contracts import ElementSegmentation

ELEMENT_RGBA = {
    "wall": (63, 169, 232, 70),
    "floor": (47, 166, 110, 70),
    "ceiling": (154, 164, 172, 60),
    "door": (232, 169, 59, 90),
    "window": (120, 200, 255, 70),
    "column": (180, 120, 255, 80),
    "stairs": (255, 210, 63, 80),
}
DAMAGE_RGBA = {
    "crack": (255, 106, 43, 230),
    "spalling": (255, 140, 60, 230),
    "exposed_rebar": (221, 74, 50, 240),
    "collapse": (221, 74, 50, 255),
    "debris": (200, 60, 70, 255),
}


def render_overlay(seg: ElementSegmentation, damage: list[dict], max_width: int = 640) -> bytes:
    h, w = seg.class_map.shape
    scale = min(1.0, max_width / w)
    ow, oh = max(1, int(w * scale)), max(1, int(h * scale))
    cm = seg.class_map
    if scale < 1.0:
        ys = (np.arange(oh) / scale).astype(int).clip(0, h - 1)
        xs = (np.arange(ow) / scale).astype(int).clip(0, w - 1)
        cm = cm[ys][:, xs]
    rgba = np.zeros((oh, ow, 4), dtype=np.uint8)
    for idx, name in seg.classes.items():
        if name in ELEMENT_RGBA:
            rgba[cm == idx] = ELEMENT_RGBA[name]
    img = Image.fromarray(rgba, "RGBA")
    draw = ImageDraw.Draw(img)
    for d in damage:
        pts = [(x * ow, y * oh) for x, y in d.get("polygon", [])]
        if len(pts) >= 3:
            color = DAMAGE_RGBA.get(d["cls"], (255, 255, 255, 255))
            draw.polygon(pts, outline=color, fill=color[:3] + (60,), width=3)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
