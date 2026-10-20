"""Zone risk fusion (HANDOFF §8.2, SRS §4.5): building-element segmentation + structural damage
→ safe / caution / unsafe / blocked, or "not analysable". Plain application code, not a model.
Thresholds live in system_settings["zone_fusion"] and must be tuned with Rescue 1122."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.ml.contracts import DamageInstance, ElementSegmentation

STRUCTURAL = ("wall", "column", "ceiling")
SURFACE_DAMAGE = ("crack", "spalling", "exposed_rebar")
OBSTRUCTION = ("collapse", "debris")


@dataclass
class FusionResult:
    status: str  # safe | caution | unsafe | blocked (meaningless when not analysable)
    risk_score: float
    confidence: float
    analysable: bool
    reasons: list[dict[str, Any]] = field(default_factory=list)  # [{key, params}] → i18n
    segmentation_summary: dict[str, float] = field(default_factory=dict)
    damage: list[dict[str, Any]] = field(default_factory=list)


def _reason(key: str, **params: Any) -> dict[str, Any]:
    return {"key": f"reasons.{key}", "params": params}


def fuse(
    seg: ElementSegmentation, damage: list[DamageInstance], cfg: dict[str, float]
) -> FusionResult:
    share = seg.share()
    structure = sum(v for k, v in share.items() if k != "other")
    summary = {k: round(v, 4) for k, v in sorted(share.items())}
    frame = seg.class_map.size or 1

    # --- not analysable: keep the previous status, never fall back to "safe" ---
    if seg.confidence < cfg["min_confidence"] or structure < cfg["min_structure_share"]:
        return FusionResult(
            status="unclassified",
            risk_score=0.0,
            confidence=round(seg.confidence, 3),
            analysable=False,
            reasons=[_reason("not_analysable", structure_pct=round(100 * structure, 1))],
            segmentation_summary=summary,
        )

    details: list[dict[str, Any]] = []
    for d in damage:
        area = d.mask.sum() / frame
        under = seg.class_map[d.mask]
        element = "other"
        if under.size:
            ids, counts = np.unique(under, return_counts=True)
            element = seg.classes.get(int(ids[counts.argmax()]), "other")
        details.append(
            {
                "cls": d.cls,
                "confidence": round(float(d.confidence), 3),
                "area_pct": round(100 * float(area), 2),
                "element": element,
                "polygon": [[round(x, 4), round(y, 4)] for x, y in d.polygon],
            }
        )

    reasons: list[dict[str, Any]] = []
    status, risk = "safe", 0.1

    # --- blocked: collapse/debris over the floor or doorway, or over much of the frame ---
    obstruction = np.zeros(seg.class_map.shape, dtype=bool)
    for d in damage:
        if d.cls in OBSTRUCTION:
            obstruction |= d.mask
    passage = seg.mask("floor", "door")
    passage_cover = (obstruction & passage).sum() / passage.sum() if passage.any() else 0.0
    frame_cover = obstruction.sum() / frame
    if passage_cover >= cfg["blocked_floor_door_share"]:
        status, risk = "blocked", 0.95
        reasons.append(_reason("passage_blocked", pct=round(100 * passage_cover, 1)))
    elif frame_cover > cfg["blocked_frame_share"]:
        status, risk = "blocked", 0.95
        reasons.append(_reason("frame_obstructed", pct=round(100 * frame_cover, 1)))

    # --- unsafe: credible collapse, or substantial surface damage on load-bearing elements ---
    if status == "safe":
        collapse = [
            d for d in damage if d.cls == "collapse" and d.confidence >= cfg["unsafe_collapse_conf"]
        ]
        structural = seg.mask(*STRUCTURAL)
        surface = np.zeros(seg.class_map.shape, dtype=bool)
        for d in damage:
            if d.cls in SURFACE_DAMAGE:
                surface |= d.mask
        surface_share = (surface & structural).sum() / frame
        rebar = [
            d
            for d in damage
            if d.cls == "exposed_rebar" and d.confidence >= cfg["unsafe_collapse_conf"]
        ]
        if collapse:
            status = "unsafe"
            risk = 0.75 + 0.1 * max(d.confidence for d in collapse)
            reasons.append(
                _reason("collapse_detected", conf=round(100 * max(d.confidence for d in collapse)))
            )
        if surface_share >= cfg["unsafe_crack_spalling_share"]:
            status = "unsafe"
            risk = max(risk, min(0.9, 0.6 + 2 * surface_share))
            reasons.append(_reason("surface_damage", pct=round(100 * surface_share, 1)))
        if rebar:
            status = "unsafe"
            risk = max(risk, 0.7)
            reasons.append(_reason("exposed_rebar"))

    # --- caution: any credible damage ---
    if status == "safe":
        credible = [d for d in damage if d.confidence >= cfg["caution_damage_conf"]]
        if credible:
            top = max(credible, key=lambda d: d.confidence)
            status = "caution"
            risk = 0.3 + 0.2 * top.confidence
            reasons.append(_reason("damage_present", cls=top.cls, conf=round(100 * top.confidence)))
        else:
            reasons.append(_reason("no_damage"))

    dmg_conf = [d.confidence for d in damage if d.confidence >= cfg["caution_damage_conf"]]
    confidence = seg.confidence if not dmg_conf else (seg.confidence + max(dmg_conf)) / 2
    return FusionResult(
        status=status,
        risk_score=round(float(risk), 3),
        confidence=round(float(confidence), 3),
        analysable=True,
        reasons=reasons,
        segmentation_summary=summary,
        damage=details,
    )
