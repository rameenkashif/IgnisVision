"""Simulation trainer (HANDOFF §9.6, SRS UC-06): reference outputs through the ML seam,
grading against the ground truth, model agreement and feedback."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.engine import SessionLocal
from app.llm.base import LLMUnavailable
from app.llm.registry import get_llm
from app.ml import runtime
from app.ml.registry import Models, reference_models
from app.models import (
    AttemptAnswer,
    MediaAsset,
    ScenarioItem,
    TrainingAttempt,
    TrainingScenario,
    User,
)
from app.services import settings as settings_svc
from app.services.media import media_url
from app.services.video import read_image, read_video_frame
from app.services.zone_fusion import fuse
from app.storage.backend import get_storage

log = logging.getLogger(__name__)

SEVERITY = {"safe": 0, "caution": 1, "unsafe": 2, "blocked": 3}
MATCH_IOU = 0.3
MIN_CROP_PX = 16


def is_video(asset: MediaAsset) -> bool:
    return asset.kind == "training_video"


def targets_of(gt: dict[str, Any]) -> list[dict[str, Any]]:
    return gt.get("regions", []) if gt.get("type") == "zone" else gt.get("people", [])


def usable(item: ScenarioItem) -> bool:
    """Items without a reference output (or without targets) are hidden (SRS UC-06 EF)."""
    return item.reference_output is not None and bool(targets_of(item.ground_truth))


def public_item(item: ScenarioItem, asset: MediaAsset) -> dict[str, Any]:
    gt = item.ground_truth
    return {
        "id": item.id,
        "order": item.order,
        "type": gt.get("type", "zone"),
        "media_kind": "video" if is_video(asset) else "image",
        "media_url": media_url(asset.id),
        "width": asset.width,
        "height": asset.height,
        "frame_s": gt.get("frame_s"),
        "regions": (
            [{"id": r["id"], "polygon": r["polygon"]} for r in gt.get("regions", [])]
            if gt.get("type") == "zone"
            else []
        ),
        "people": (
            [{"id": p["id"], "bbox": p["bbox"]} for p in gt.get("people", [])]
            if gt.get("type") == "posture"
            else []
        ),
    }


async def items_with_media(
    db: AsyncSession, scenario_id: uuid.UUID, only_usable: bool = True
) -> list[tuple[ScenarioItem, MediaAsset]]:
    rows = (
        await db.execute(
            select(ScenarioItem, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ScenarioItem.media_id)
            .where(ScenarioItem.scenario_id == scenario_id)
            .order_by(ScenarioItem.order, ScenarioItem.created_at)
        )
    ).all()
    return [(i, a) for i, a in rows if usable(i) or not only_usable]


# ---------------------------------------------------------------- reference output


def _iou(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _zone_reference(
    image: np.ndarray, gt: dict[str, Any], models: Models, cfg: dict[str, float]
) -> dict[str, Any]:
    """Each labelled region is cropped (its bounding box) and run through segmentation +
    damage + zone fusion, exactly like a live zone frame."""
    h, w = image.shape[:2]
    out: dict[str, Any] = {}
    for r in gt["regions"]:
        xs = [p[0] for p in r["polygon"]]
        ys = [p[1] for p in r["polygon"]]
        x1, x2 = int(min(xs) * w), int(max(xs) * w)
        y1, y2 = int(min(ys) * h), int(max(ys) * h)
        if x2 - x1 < MIN_CROP_PX or y2 - y1 < MIN_CROP_PX:
            out[r["id"]] = {"status": None, "analysable": False, "confidence": 0.0,
                            "reasons": [{"key": "reasons.not_analysable",
                                         "params": {"structure_pct": 0}}]}  # fmt: skip
            continue
        crop = np.ascontiguousarray(image[y1:y2, x1:x2])
        res = fuse(models.segmenter.predict(crop), models.damage.predict(crop), cfg)
        out[r["id"]] = {
            "status": res.status if res.analysable else None,
            "analysable": res.analysable,
            "confidence": res.confidence,
            "risk_score": res.risk_score,
            "reasons": res.reasons,
        }
    return {"type": "zone", "regions": out}


def _posture_reference(image: np.ndarray, gt: dict[str, Any], models: Models) -> dict[str, Any]:
    """Detections are matched to the labelled people greedily by IoU (≥ 0.3)."""
    dets = models.pose.predict(image, None)
    pairs = sorted(
        (
            (_iou(tuple(p["bbox"]), d.bbox), p["id"], j)
            for p in gt["people"]
            for j, d in enumerate(dets)
        ),
        reverse=True,
    )
    out: dict[str, Any] = {p["id"]: {"posture": None, "detected": False} for p in gt["people"]}
    used: set[int] = set()
    for iou, pid, j in pairs:
        if iou < MATCH_IOU or j in used or out[pid]["detected"]:
            continue
        d = dets[j]
        used.add(j)
        out[pid] = {
            "posture": d.posture,
            "detected": True,
            "posture_confidence": round(d.posture_confidence, 3),
            "detection_confidence": round(d.detection_confidence, 3),
            "bbox": [round(c, 4) for c in d.bbox],
            "iou": round(iou, 3),
        }
    return {"type": "posture", "people": out, "unmatched_detections": len(dets) - len(used)}


def _versions(models: Models, kind: str) -> str:
    ms = (models.segmenter, models.damage) if kind == "zone" else (models.pose,)
    return "; ".join(f"{m.name} {m.version}" for m in ms)


def _load_frame(asset: MediaAsset, frame_s: float | None) -> np.ndarray:
    path = str(get_storage().path(asset.storage_key))
    return read_video_frame(path, frame_s or 0.0) if is_video(asset) else read_image(path)


async def compute_reference(db: AsyncSession, item: ScenarioItem) -> bool:
    """Runs the ML seam over one item and stores the result. False when the item has no
    targets yet (it stays hidden from trainees)."""
    gt = item.ground_truth
    if not targets_of(gt):
        item.reference_output = item.reference_model_version = None
        return False
    asset = await db.get(MediaAsset, item.media_id)
    models = reference_models()
    cfg = (await settings_svc.load_all(db))["zone_fusion"]
    image = await runtime.run(_load_frame, asset, gt.get("frame_s"))
    if gt["type"] == "zone":
        ref = await runtime.run(_zone_reference, image, gt, models, cfg)
    else:
        ref = await runtime.run(_posture_reference, image, gt, models)
    ref["backend"] = models.backend
    item.reference_output = ref
    item.reference_model_version = _versions(models, gt["type"])
    return True


def model_label(item: ScenarioItem, target_id: str) -> str | None:
    ref = item.reference_output or {}
    if ref.get("type") == "zone":
        return (ref.get("regions", {}).get(target_id) or {}).get("status")
    return (ref.get("people", {}).get(target_id) or {}).get("posture")


# ---------------------------------------------------------------- grading


def grade_item(
    item: ScenarioItem, answer: dict[str, Any], grading: dict[str, Any]
) -> list[dict[str, Any]]:
    gt = item.ground_truth
    zone = gt["type"] == "zone"
    given = answer.get("regions" if zone else "people", {})
    results = []
    for t in targets_of(gt):
        truth = t["status"] if zone else t["posture"]
        ans = given.get(t["id"])
        model = model_label(item, t["id"])
        credit = 1.0 if ans == truth else 0.0
        if (
            zone
            and credit == 0.0
            and ans in SEVERITY
            and grading.get("partial_credit_adjacent")
            and abs(SEVERITY[ans] - SEVERITY[truth]) == 1
        ):
            credit = float(grading.get("adjacent_credit", 0.5))
        results.append(
            {
                "id": t["id"],
                "answer": ans,
                "truth": truth,
                "model": model,
                "credit": credit,
                "correct": credit == 1.0,
                "agrees_with_model": None if model is None or ans is None else ans == model,
            }
        )
    return results


async def submit(
    db: AsyncSession, attempt: TrainingAttempt, answers: dict[uuid.UUID, dict[str, Any]]
) -> None:
    grading = (await settings_svc.load_all(db))["trainer.grading"]
    items = await items_with_media(db, attempt.scenario_id)
    credit = total = agree = agree_n = 0.0
    per_item = []
    for item, _ in items:
        ans = answers.get(item.id, {"regions": {}, "people": {}})
        results = grade_item(item, ans, grading)
        score = sum(r["credit"] for r in results) / len(results)
        db.add(
            AttemptAnswer(
                attempt_id=attempt.id,
                item_id=item.id,
                answer=ans,
                is_correct=all(r["correct"] for r in results),
                per_target_results={"targets": results, "score": round(score, 4)},
            )
        )
        credit += sum(r["credit"] for r in results)
        total += len(results)
        for r in results:
            if r["agrees_with_model"] is not None:
                agree_n += 1
                agree += r["agrees_with_model"]
        per_item.append({"item_id": str(item.id), "score": round(score, 4)})
    attempt.score_pct = round(100 * credit / total, 1) if total else 0.0
    attempt.feedback = {
        "items": per_item,
        "correct_targets": int(credit) if credit.is_integer() else round(credit, 1),
        "total_targets": int(total),
        "model_agreement_pct": round(100 * agree / agree_n, 1) if agree_n else None,
        "model_agreement_n": int(agree_n),
        "grading": grading,
        "llm": "pending" if await _llm_wanted(db) else "off",
    }
    attempt.submitted_at = datetime.now(UTC)


# ---------------------------------------------------------------- LLM feedback (optional)

FEEDBACK_SYSTEM = (
    "You are a fire-rescue instructor for Rescue 1122 giving feedback on a training exercise. "
    "The trainee labelled zone safety (safe/caution/unsafe/blocked) or victim posture "
    "(standing/sitting/lying/bending). Explain briefly WHY each wrong label differs from the "
    "correct answer, using ONLY the explanation text and model reasons provided. Do not invent "
    "observations about the images. Be encouraging and concrete; at most 6 short sentences or "
    "bullets. Write in {language}."
)


async def _llm_wanted(db: AsyncSession) -> bool:
    flags = (await settings_svc.load_all(db))["llm.features"]
    return bool(flags.get("trainer_feedback")) and get_llm().name != "template"


async def _facts(db: AsyncSession, attempt: TrainingAttempt) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(AttemptAnswer, ScenarioItem)
            .join(ScenarioItem, ScenarioItem.id == AttemptAnswer.item_id)
            .where(AttemptAnswer.attempt_id == attempt.id)
            .order_by(ScenarioItem.order)
        )
    ).all()
    items = []
    for ans, item in rows:
        wrong = [t for t in ans.per_target_results["targets"] if not t["correct"]]
        if not wrong:
            continue
        ref = item.reference_output or {}
        reasons = {
            t["id"]: [r["key"].removeprefix("reasons.") + json.dumps(r.get("params", {}))
                      for r in (ref.get("regions", {}).get(t["id"]) or {}).get("reasons", [])]
            for t in wrong
        }  # fmt: skip
        items.append(
            {
                "type": item.ground_truth["type"],
                "mistakes": wrong,
                "explanation": item.ground_truth.get("explanation_en", ""),
                "explanation_ur": item.ground_truth.get("explanation_ur", ""),
                "model_reasons": reasons,
            }
        )
    return {"score_pct": attempt.score_pct, "items": items}


async def llm_feedback_for(attempt_id: uuid.UUID) -> None:
    """Background: write LLM feedback in the trainee's language; on any failure the template
    feedback (explanations shown per item) is all the trainee sees."""
    async with SessionLocal() as db:
        attempt = await db.get(TrainingAttempt, attempt_id)
        if attempt is None or not await _llm_wanted(db):
            return
        user = await db.get(User, attempt.user_id)
        lang = user.preferred_language if user else "en"
        facts = await _facts(db, attempt)
        status = "done"
        if not facts["items"]:
            attempt.llm_feedback = None
            status = "none"
        else:
            try:
                attempt.llm_feedback = await get_llm().complete(
                    FEEDBACK_SYSTEM.format(language="Urdu (اردو)" if lang == "ur" else "English"),
                    [{"role": "user", "content": json.dumps(facts, ensure_ascii=False)}],
                    max_tokens=800,
                    lang=lang,  # type: ignore[arg-type]
                )
            except LLMUnavailable as e:
                log.info("trainer feedback: template kept (%s)", e)
                status = "failed"
        attempt.feedback = {**(attempt.feedback or {}), "llm": status}
        await db.commit()


_background: set[asyncio.Task] = set()


def schedule_feedback(attempt_id: uuid.UUID) -> None:
    task = asyncio.get_running_loop().create_task(llm_feedback_for(attempt_id))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def scenario_counts(db: AsyncSession, scenario_id: uuid.UUID) -> tuple[int, int]:
    items = await items_with_media(db, scenario_id, only_usable=False)
    return len(items), sum(1 for i, _ in items if usable(i))


async def get_scenario(db: AsyncSession, scenario_id: uuid.UUID) -> TrainingScenario:
    sc = await db.get(TrainingScenario, scenario_id)
    if sc is None:
        raise AppError(404, "scenario_not_found")
    return sc
