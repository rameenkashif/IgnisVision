"""Placeholder training scenarios (DECISIONS Q2): generated images with hand-written ground
truth, clearly marked PLACEHOLDER, until Rescue 1122 provides real scenario media."""

import io
import logging
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ScenarioItem, TrainingScenario
from app.services import training as training_svc
from app.services.media import store_media

log = logging.getLogger(__name__)

W, H = 960, 640
STATUS = ("safe", "caution", "unsafe", "blocked")
DARK_TARGET = (0.0, 0.013, 0.10, 0.30)  # share of very dark pixels per damage level


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _watermark(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 250, 40], fill=(200, 40, 40))
    d.text((12, 6), "PLACEHOLDER", fill=(255, 235, 235), font=_font(26))


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _dark_share(a: np.ndarray) -> float:
    return float(((a @ np.array([0.299, 0.587, 0.114])) < 50).mean())


def _room(w: int, h: int, level: int, rng: np.random.Generator) -> Image.Image:
    """One cell: ceiling, wall, floor; damage painted in very dark tones (cracks, spalling,
    debris) until the dark-pixel share reaches the level's target."""
    img = Image.new("RGB", (w, h), (214, 200, 176))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, int(h * 0.2)], fill=(198, 198, 204))
    d.rectangle([0, int(h * 0.75), w, h], fill=(150, 122, 92))
    d.rectangle([int(w * 0.62), int(h * 0.35), int(w * 0.76), int(h * 0.75)], fill=(120, 92, 70))
    d.rectangle([0, int(h * 0.2), int(w * 0.06), int(h * 0.75)], fill=(185, 180, 172))
    target = DARK_TARGET[level]
    dark, debris = (28, 26, 24), (34, 29, 25)
    for _ in range(400):
        if _dark_share(np.asarray(img, dtype=np.float32)) >= target:
            break
        if level == 3:
            cx, cy = rng.uniform(0, w), rng.uniform(h * 0.55, h)
            r = rng.uniform(0.04, 0.12) * w
            pts = [(cx + r * np.cos(t) * rng.uniform(0.6, 1), cy + r * np.sin(t) * rng.uniform(0.5, 1))
                   for t in np.linspace(0, 2 * np.pi, 9)]  # fmt: skip
            d.polygon(pts, fill=debris)
        else:
            x, y = rng.uniform(0.1, 0.55) * w, rng.uniform(0.25, 0.4) * h
            pts = [(x, y)]
            for _ in range(int(rng.integers(4, 9))):
                x += rng.uniform(-0.05, 0.08) * w
                y += rng.uniform(0.02, 0.07) * h
                pts.append((x, min(y, h * 0.74)))
            d.line(pts, fill=dark, width=3 if level == 1 else 7)
            if level == 2 and rng.uniform() < 0.4:  # spalling patch
                sx, sy = rng.uniform(0.1, 0.5) * w, rng.uniform(0.25, 0.6) * h
                d.ellipse([sx, sy, sx + 0.08 * w, sy + 0.06 * h], fill=dark)
    a = np.asarray(img, dtype=np.float32) + rng.normal(0, 5, (h, w, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def zone_image(rows: int, cols: int, levels: list[int], seed: int) -> tuple[bytes, list[list]]:
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (W, H))
    cw, ch = W // cols, H // rows
    polys = []
    for i, level in enumerate(levels):
        r, c = divmod(i, cols)
        img.paste(_room(cw, ch, level, rng), (c * cw, r * ch))
        x0, y0, x1, y1 = c / cols, r / rows, (c + 1) / cols, (r + 1) / rows
        polys.append([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    d = ImageDraw.Draw(img)
    for c in range(1, cols):
        d.line([(c * cw, 0), (c * cw, H)], fill=(235, 235, 235), width=3)
    for r in range(1, rows):
        d.line([(0, r * ch), (W, r * ch)], fill=(235, 235, 235), width=3)
    _watermark(img)
    return _png(img), polys


def _person(d: ImageDraw.ImageDraw, box: tuple[float, ...], posture: str) -> None:
    x1, y1, x2, y2 = (box[0] * W, box[1] * H, box[2] * W, box[3] * H)
    bw, bh = x2 - x1, y2 - y1
    hot, warm = (255, 246, 210), (250, 170, 60)
    if posture == "lying":
        d.ellipse([x1, y1 + bh * 0.2, x2 - bw * 0.2, y2], fill=warm)
        d.ellipse([x2 - bw * 0.25, y1, x2, y1 + bh * 0.8], fill=hot)
    elif posture == "sitting":
        d.ellipse([x1 + bw * 0.3, y1, x1 + bw * 0.75, y1 + bh * 0.25], fill=hot)
        d.rectangle([x1 + bw * 0.25, y1 + bh * 0.25, x1 + bw * 0.75, y1 + bh * 0.7], fill=warm)
        d.rectangle([x1 + bw * 0.25, y1 + bh * 0.62, x2, y1 + bh * 0.78], fill=warm)
    elif posture == "bending":
        d.ellipse([x2 - bw * 0.35, y1 + bh * 0.25, x2, y1 + bh * 0.5], fill=hot)
        d.polygon([(x1, y1 + bh * 0.3), (x2 - bw * 0.3, y1 + bh * 0.3),
                   (x1 + bw * 0.5, y2), (x1, y2)], fill=warm)  # fmt: skip
    else:  # standing
        d.ellipse([x1 + bw * 0.25, y1, x2 - bw * 0.25, y1 + bh * 0.2], fill=hot)
        d.rectangle([x1 + bw * 0.15, y1 + bh * 0.2, x2 - bw * 0.15, y2], fill=warm)


def posture_image(postures: list[str], seed: int) -> tuple[bytes, list[list[float]]]:
    """Thermal-looking scene; people sit where the mock detector looks (x = 0.15 + 0.3·i)."""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 1, H)[:, None, None]
    base = (1 - yy) * np.array([22, 12, 70]) + yy * np.array([70, 24, 96])
    a = np.broadcast_to(base, (H, W, 3)) + rng.normal(0, 6, (H, W, 3))
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    boxes = []
    for i, p in enumerate(postures):
        cx = 0.15 + 0.3 * i
        bw, bh = (0.28, 0.14) if p == "lying" else (0.12, 0.36)
        cy = 0.7 if p == "lying" else 0.55
        box = [round(max(0.0, cx - bw / 2), 3), round(cy - bh / 2, 3),
               round(min(1.0, cx + bw / 2), 3), round(cy + bh / 2, 3)]  # fmt: skip
        _person(d, tuple(box), p)
        boxes.append(box)
    _watermark(img)
    return _png(img), boxes


ZONE_EXPLAIN = {
    "safe": ("No visible damage on walls, columns or ceiling; the passage is clear.",
             "دیواروں، ستونوں یا چھت پر کوئی نقصان نظر نہیں آتا؛ راستہ صاف ہے۔"),
    "caution": ("Hairline cracks only, on a non-structural wall: enter with care and keep watching.",
                "صرف باریک دراڑیں، غیر ساختی دیوار پر: احتیاط سے داخل ہوں اور نظر رکھیں۔"),
    "unsafe": ("Wide cracks with spalling on the wall: the structure may fail. Do not enter.",
               "دیوار پر چوڑی دراڑیں اور پلستر اکھڑا ہوا: ڈھانچہ گر سکتا ہے۔ داخل نہ ہوں۔"),
    "blocked": ("Debris covers the floor and doorway: the zone cannot be passed.",
                "ملبہ فرش اور دروازے کو ڈھانپے ہوئے ہے: اس زون سے گزرا نہیں جا سکتا۔"),
}  # fmt: skip

POSTURE_EXPLAIN = (
    "Lying people are the highest rescue priority; sitting and bending people may be injured; "
    "standing people can usually move by themselves.",
    "لیٹے ہوئے افراد کو بچانا سب سے پہلے ضروری ہے؛ بیٹھے اور جھکے ہوئے افراد زخمی ہو سکتے ہیں؛ "
    "کھڑے افراد عموماً خود چل سکتے ہیں۔",
)

# (title_en, title_ur, desc_en, desc_ur, difficulty, kind, items)
# zone item: ("zone", rows, cols, painted levels, ground-truth statuses, extra explanation)
# posture item: ("posture", postures)
SCENARIOS: list[tuple[Any, ...]] = [
    (
        "Zone status: corridor after a fire (PLACEHOLDER)",
        "زون کی حالت: آگ کے بعد راہداری (پلیس ہولڈر)",
        "PLACEHOLDER media. Label each part of the corridor as safe, caution, unsafe or blocked.",
        "پلیس ہولڈر میڈیا۔ راہداری کے ہر حصے کو محفوظ، احتیاط، غیر محفوظ یا بند کے طور پر نشان زد کریں۔",
        1,
        "zone",
        [
            ("zone", 2, 2, [0, 1, 2, 3], ["safe", "caution", "unsafe", "blocked"], None),
            ("zone", 1, 3, [1, 0, 1], ["caution", "safe", "unsafe"],
             ("The right-hand crack runs through a load-bearing column: treat it as unsafe even "
              "though it is thin.",
              "دائیں جانب کی دراڑ بوجھ اٹھانے والے ستون سے گزرتی ہے: باریک ہونے کے باوجود اسے غیر "
              "محفوظ سمجھیں۔")),
        ],
    ),
    (
        "Posture: people in a smoke-filled room (PLACEHOLDER)",
        "جسمانی حالت: دھویں سے بھرے کمرے میں افراد (پلیس ہولڈر)",
        "PLACEHOLDER thermal images. Pick the posture of every person.",
        "پلیس ہولڈر تھرمل تصاویر۔ ہر فرد کی جسمانی حالت منتخب کریں۔",
        2,
        "posture",
        [("posture", ["standing", "lying", "sitting"]), ("posture", ["lying", "bending"])],
    ),
    (
        "Mixed: after a partial collapse (PLACEHOLDER)",
        "مخلوط: جزوی انہدام کے بعد (پلیس ہولڈر)",
        "PLACEHOLDER media. Classify the zones, then the people found inside.",
        "پلیس ہولڈر میڈیا۔ پہلے زونز کی درجہ بندی کریں، پھر اندر ملنے والے افراد کی۔",
        3,
        "mixed",
        [
            ("zone", 1, 2, [3, 2], ["blocked", "unsafe"], None),
            ("posture", ["lying", "lying", "standing"]),
        ],
    ),
]  # fmt: skip


def _ground_truth(spec: tuple[Any, ...], seed: int) -> tuple[bytes, dict[str, Any]]:
    if spec[0] == "zone":
        _, rows, cols, levels, statuses, extra = spec
        png, polys = zone_image(rows, cols, levels, seed)
        regions = [{"id": f"r{i + 1}", "polygon": p, "status": s}
                   for i, (p, s) in enumerate(zip(polys, statuses, strict=True))]  # fmt: skip
        en = " ".join(dict.fromkeys(ZONE_EXPLAIN[s][0] for s in statuses))
        ur = " ".join(dict.fromkeys(ZONE_EXPLAIN[s][1] for s in statuses))
        if extra:
            en, ur = f"{en} {extra[0]}", f"{ur} {extra[1]}"
        gt = {"type": "zone", "regions": regions, "people": []}
    else:
        png, boxes = posture_image(spec[1], seed)
        people = [{"id": f"p{i + 1}", "bbox": b, "posture": p}
                  for i, (b, p) in enumerate(zip(boxes, spec[1], strict=True))]  # fmt: skip
        en, ur = POSTURE_EXPLAIN
        gt = {"type": "posture", "regions": [], "people": people}
    gt |= {"explanation_en": f"PLACEHOLDER — {en}", "explanation_ur": f"پلیس ہولڈر — {ur}",
           "frame_s": None}  # fmt: skip
    return png, gt


async def seed_placeholder_scenarios(db: AsyncSession, created_by: Any = None) -> list[str]:
    """Idempotent by title; returns the titles created."""
    created = []
    for n, (title_en, title_ur, d_en, d_ur, difficulty, kind, items) in enumerate(SCENARIOS):
        exists = (
            await db.execute(
                select(TrainingScenario.id).where(TrainingScenario.title_en == title_en)
            )
        ).first()
        if exists:
            continue
        sc = TrainingScenario(
            title_en=title_en, title_ur=title_ur, description_en=d_en, description_ur=d_ur,
            difficulty=difficulty, kind=kind, is_active=True, is_placeholder=True,
            created_by=created_by,
        )  # fmt: skip
        db.add(sc)
        await db.flush()
        for order, spec in enumerate(items):
            png, gt = _ground_truth(spec, seed=1000 * n + order)
            asset = await store_media(
                db, key=f"training/{sc.id}/placeholder-{order + 1}.png", data=png,
                kind="training_image", mime="image/png", source="seed", width=W, height=H,
            )  # fmt: skip
            item = ScenarioItem(scenario_id=sc.id, order=order, media_id=asset.id, ground_truth=gt)
            db.add(item)
            await db.flush()
            try:
                await training_svc.compute_reference(db, item)
            except Exception:  # noqa: BLE001 — e.g. real weights missing: recompute later
                log.exception("placeholder reference failed; run recompute-reference later")
        created.append(title_en)
    return created
