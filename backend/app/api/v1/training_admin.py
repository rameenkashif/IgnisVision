"""Scenario management for admins (HANDOFF §7.1 training admin, §9.6)."""

import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.ml import runtime
from app.ml.registry import reference_models
from app.models import MediaAsset, ScenarioItem, TrainingScenario, User
from app.schemas.training import (
    AdminItem,
    AdminScenario,
    AdminScenarioDetail,
    GroundTruth,
    ItemPatch,
    RecomputeOut,
    ScenarioIn,
    ScenarioPatch,
)
from app.schemas.users import Confirm
from app.services import audit
from app.services import training as svc
from app.services.media import media_url
from app.services.video import VideoSampler, probe_image
from app.storage.backend import get_storage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/scenarios", tags=["training admin"])
Admin = Annotated[User, Depends(require_roles("admin"))]

IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}
VIDEO_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024
FIELDS = ("title_en", "title_ur", "description_en", "description_ur", "difficulty", "kind",
          "is_active")  # fmt: skip


def _snapshot(sc: TrainingScenario) -> dict[str, Any]:
    return {f: getattr(sc, f) for f in FIELDS}


async def _admin_summary(db: DB, sc: TrainingScenario) -> dict[str, Any]:
    total, n_usable = await svc.scenario_counts(db, sc.id)
    return _snapshot(sc) | {
        "id": sc.id, "is_placeholder": sc.is_placeholder, "item_count": total,
        "usable_count": n_usable, "created_at": sc.created_at,
    }  # fmt: skip


def _admin_item(item: ScenarioItem, asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": item.id, "order": item.order, "media_id": asset.id,
        "media_kind": "video" if svc.is_video(asset) else "image",
        "media_url": media_url(asset.id), "width": asset.width, "height": asset.height,
        "duration_s": asset.duration_s, "ground_truth": item.ground_truth,
        "reference_output": item.reference_output,
        "reference_model_version": item.reference_model_version, "usable": svc.usable(item),
    }  # fmt: skip


async def _detail(db: DB, sc: TrainingScenario) -> dict[str, Any]:
    items = await svc.items_with_media(db, sc.id, only_usable=False)
    return await _admin_summary(db, sc) | {"items": [_admin_item(i, a) for i, a in items]}


@router.get("", response_model=list[AdminScenario])
async def list_scenarios(_: Admin, db: DB) -> list[dict[str, Any]]:
    rows = (
        await db.execute(select(TrainingScenario).order_by(TrainingScenario.created_at))
    ).scalars()
    return [await _admin_summary(db, sc) for sc in rows]


@router.post("", response_model=AdminScenarioDetail, status_code=201)
async def create_scenario(
    body: ScenarioIn, request: Request, admin: Admin, db: DB
) -> dict[str, Any]:
    sc = TrainingScenario(**body.model_dump(), created_by=admin.id)
    db.add(sc)
    await db.flush()
    await audit.record(
        db,
        actor_id=admin.id,
        action="scenario.create",
        entity_type="scenario",
        entity_id=sc.id,
        after=_snapshot(sc),
        request=request,
    )
    await db.commit()
    await db.refresh(sc)
    return await _detail(db, sc)


@router.get("/{scenario_id}", response_model=AdminScenarioDetail)
async def get_scenario(scenario_id: uuid.UUID, _: Admin, db: DB) -> dict[str, Any]:
    return await _detail(db, await svc.get_scenario(db, scenario_id))


@router.patch("/{scenario_id}", response_model=AdminScenarioDetail)
async def update_scenario(
    scenario_id: uuid.UUID, body: ScenarioPatch, request: Request, admin: Admin, db: DB
) -> dict[str, Any]:
    sc = await svc.get_scenario(db, scenario_id)
    before = _snapshot(sc)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None and k not in ("description_en", "description_ur"):
            continue
        setattr(sc, k, v)
    await audit.record(
        db,
        actor_id=admin.id,
        action="scenario.update",
        entity_type="scenario",
        entity_id=sc.id,
        before=before,
        after=_snapshot(sc),
        request=request,
    )
    await db.commit()
    await db.refresh(sc)
    return await _detail(db, sc)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: uuid.UUID, body: Confirm, request: Request, admin: Admin, db: DB
) -> None:
    """Deletes the scenario, its items and every attempt at it (confirmation + audit)."""
    if not body.confirm:
        raise AppError(400, "confirmation_required")
    sc = await svc.get_scenario(db, scenario_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="scenario.delete",
        entity_type="scenario",
        entity_id=sc.id,
        before=_snapshot(sc),
        request=request,
    )
    await db.delete(sc)
    await db.commit()


@router.post("/{scenario_id}/items", response_model=AdminItem, status_code=201)
async def add_item(
    scenario_id: uuid.UUID,
    request: Request,
    admin: Admin,
    db: DB,
    file: Annotated[UploadFile, File(description="Image (JPEG/PNG) or video (MP4/WebM/MOV)")],
    ground_truth: Annotated[str | None, Form(description="JSON, HANDOFF §9.6 format")] = None,
) -> dict[str, Any]:
    sc = await svc.get_scenario(db, scenario_id)
    gt = _parse_gt(ground_truth, sc.kind)
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype in IMAGE_TYPES:
        kind, ext, limit = "training_image", IMAGE_TYPES[ctype], MAX_IMAGE_BYTES
    elif ctype in VIDEO_TYPES:
        kind, ext, limit = "training_video", VIDEO_TYPES[ctype], MAX_VIDEO_BYTES
    else:
        raise AppError(415, "unsupported_media_type", {"type": ctype})
    media_id = uuid.uuid4()
    key = f"training/{sc.id}/{media_id}{ext}"
    storage = get_storage()
    try:
        size, sha = await runtime.run(storage.save_stream, key, file.file, limit)
    except ValueError as e:
        raise AppError(413, "file_too_large", {"max_mb": limit // (1024 * 1024)}) from e
    path = str(storage.path(key))
    duration = None
    try:
        if kind == "training_image":
            width, height = await runtime.run(probe_image, path)
        else:
            sampler = await runtime.run(VideoSampler, path)
            width, height, duration = sampler.width, sampler.height, sampler.duration_s
            sampler.close()
    except Exception as e:
        storage.delete(key)
        raise AppError(422, "unreadable_media") from e
    db.add(
        MediaAsset(id=media_id, kind=kind, storage_key=key, mime=ctype, bytes=size, width=width,
                   height=height, duration_s=duration, sha256=sha, uploaded_by=admin.id,
                   source="web_upload")
    )  # fmt: skip
    await db.flush()
    order = (
        await db.execute(
            select(func.coalesce(func.max(ScenarioItem.order), -1)).where(
                ScenarioItem.scenario_id == sc.id
            )
        )
    ).scalar_one() + 1
    item = ScenarioItem(scenario_id=sc.id, order=order, media_id=media_id, ground_truth=gt)
    db.add(item)
    await db.flush()
    await _recompute_one(db, item)
    await audit.record(
        db,
        actor_id=admin.id,
        action="scenario.item_add",
        entity_type="scenario",
        entity_id=sc.id,
        after={"item_id": str(item.id)},
        request=request,
    )
    await db.commit()
    asset = await db.get(MediaAsset, media_id)
    return _admin_item(item, asset)


@router.patch("/{scenario_id}/items/{item_id}", response_model=AdminItem)
async def update_item(
    scenario_id: uuid.UUID, item_id: uuid.UUID, body: ItemPatch, admin: Admin, db: DB
) -> dict[str, Any]:
    """Saving new ground truth recomputes that item's reference output straight away."""
    item = await _item(db, scenario_id, item_id)
    if body.order is not None:
        item.order = body.order
    if body.ground_truth is not None:
        item.ground_truth = body.ground_truth.model_dump()
        await _recompute_one(db, item)
    await db.commit()
    return _admin_item(item, await db.get(MediaAsset, item.media_id))


@router.delete("/{scenario_id}/items/{item_id}", status_code=204)
async def delete_item(
    scenario_id: uuid.UUID, item_id: uuid.UUID, request: Request, admin: Admin, db: DB
) -> None:
    item = await _item(db, scenario_id, item_id)
    await audit.record(
        db,
        actor_id=admin.id,
        action="scenario.item_delete",
        entity_type="scenario",
        entity_id=scenario_id,
        before={"item_id": str(item.id)},
        request=request,
    )
    await db.delete(item)
    await db.commit()


@router.post("/{scenario_id}/recompute-reference", response_model=RecomputeOut)
async def recompute_reference(scenario_id: uuid.UUID, _: Admin, db: DB) -> dict[str, Any]:
    """Runs the ML seam over every item (e.g. after a model update, MODEL_INTEGRATION.md)."""
    sc = await svc.get_scenario(db, scenario_id)
    computed = skipped = failed = 0
    for item, _a in await svc.items_with_media(db, sc.id, only_usable=False):
        res = await _recompute_one(db, item)
        computed += res is True
        skipped += res is False
        failed += res is None
    await db.commit()
    models = reference_models()
    return {
        "computed": computed,
        "skipped": skipped,
        "failed": failed,
        "model_version": "; ".join(f"{k} {v}" for k, v in models.versions().items()),
    }


async def _recompute_one(db: DB, item: ScenarioItem) -> bool | None:
    """True computed, False no targets yet, None model failure (item stays hidden)."""
    try:
        return await svc.compute_reference(db, item)
    except Exception:  # noqa: BLE001 — a broken model must not break the admin screen
        log.exception("reference output failed for item %s", item.id)
        item.reference_output = item.reference_model_version = None
        return None


async def _item(db: DB, scenario_id: uuid.UUID, item_id: uuid.UUID) -> ScenarioItem:
    item = await db.get(ScenarioItem, item_id)
    if item is None or item.scenario_id != scenario_id:
        raise AppError(404, "item_not_found")
    return item


def _parse_gt(raw: str | None, kind: str) -> dict[str, Any]:
    if not raw:
        return GroundTruth(type="posture" if kind == "posture" else "zone").model_dump()
    try:
        return GroundTruth.model_validate(json.loads(raw)).model_dump()
    except (ValueError, ValidationError) as e:
        raise AppError(422, "invalid_ground_truth", {"detail": str(e)[:300]}) from e
