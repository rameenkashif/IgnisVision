"""Simulation trainer for trainees, responders, commanders and training staff (HANDOFF §9.6)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.deps import DB, require_roles
from app.core.errors import AppError
from app.models import (
    AttemptAnswer,
    MediaAsset,
    ScenarioItem,
    TrainingAttempt,
    TrainingScenario,
    User,
)
from app.schemas.training import (
    AttemptOut,
    AttemptSummary,
    ScenarioDetail,
    ScenarioSummary,
    SubmitIn,
)
from app.services import training as svc

router = APIRouter(prefix="/training", tags=["training"])
ATTEMPTERS = ("incident_commander", "field_responder", "training_staff", "trainee")
ALL_RESULTS = ("admin", "incident_commander", "training_staff")
Attempter = Annotated[User, Depends(require_roles(*ATTEMPTERS))]
ResultReader = Annotated[User, Depends(require_roles(*ATTEMPTERS, "admin"))]


async def _summary(db: DB, sc: TrainingScenario, user: User | None) -> dict[str, Any]:
    items = await svc.items_with_media(db, sc.id)
    out: dict[str, Any] = {
        "id": sc.id, "title_en": sc.title_en, "title_ur": sc.title_ur,
        "description_en": sc.description_en, "description_ur": sc.description_ur,
        "difficulty": sc.difficulty, "kind": sc.kind, "is_placeholder": sc.is_placeholder,
        "item_count": len(items),
    }  # fmt: skip
    if user is not None:
        n, best = (
            await db.execute(
                select(func.count(), func.max(TrainingAttempt.score_pct)).where(
                    TrainingAttempt.scenario_id == sc.id,
                    TrainingAttempt.user_id == user.id,
                    TrainingAttempt.submitted_at.is_not(None),
                )
            )
        ).one()
        out |= {"attempts": n, "best_score": best}
    return out


async def _active(db: DB, scenario_id: uuid.UUID) -> TrainingScenario:
    sc = await svc.get_scenario(db, scenario_id)
    if not sc.is_active:
        raise AppError(404, "scenario_not_found")
    return sc


@router.get("/scenarios", response_model=list[ScenarioSummary])
async def list_scenarios(user: Attempter, db: DB) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(TrainingScenario)
            .where(TrainingScenario.is_active.is_(True))
            .order_by(TrainingScenario.difficulty, TrainingScenario.title_en)
        )
    ).scalars()
    out = [await _summary(db, sc, user) for sc in rows]
    return [s for s in out if s["item_count"] > 0]  # nothing usable → hidden


@router.get("/scenarios/{scenario_id}", response_model=ScenarioDetail)
async def get_scenario(scenario_id: uuid.UUID, user: Attempter, db: DB) -> dict[str, Any]:
    sc = await _active(db, scenario_id)
    items = await svc.items_with_media(db, sc.id)
    return await _summary(db, sc, user) | {"items": [svc.public_item(i, a) for i, a in items]}


@router.post("/scenarios/{scenario_id}/attempts", response_model=AttemptOut, status_code=201)
async def start_attempt(scenario_id: uuid.UUID, user: Attempter, db: DB) -> dict[str, Any]:
    sc = await _active(db, scenario_id)
    if not await svc.items_with_media(db, sc.id):
        raise AppError(409, "scenario_not_ready")
    attempt = TrainingAttempt(scenario_id=sc.id, user_id=user.id)
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return await _attempt_out(db, attempt, user)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptOut)
async def submit_attempt(
    attempt_id: uuid.UUID, body: SubmitIn, user: Attempter, db: DB
) -> dict[str, Any]:
    attempt = await db.get(TrainingAttempt, attempt_id, with_for_update=True)
    if attempt is None or attempt.user_id != user.id:
        raise AppError(404, "attempt_not_found")
    if attempt.submitted_at is not None:
        raise AppError(409, "attempt_already_submitted")
    await svc.submit(db, attempt, {k: v.model_dump() for k, v in body.answers.items()})
    await db.commit()
    await db.refresh(attempt)
    if (attempt.feedback or {}).get("llm") == "pending":
        svc.schedule_feedback(attempt.id)
    return await _attempt_out(db, attempt, user)


@router.get("/attempts", response_model=list[AttemptSummary])
async def list_attempts(
    user: ResultReader,
    db: DB,
    user_id: uuid.UUID | None = None,
    scenario_id: uuid.UUID | None = None,
    submitted_only: bool = True,
) -> list[dict[str, Any]]:
    """Own attempts; commanders, training staff and admins may see everyone's (HANDOFF §6)."""
    if user.role not in ALL_RESULTS:
        if user_id not in (None, user.id):
            raise AppError(403, "forbidden")
        user_id = user.id
    stmt = (
        select(TrainingAttempt, TrainingScenario, User)
        .join(TrainingScenario, TrainingScenario.id == TrainingAttempt.scenario_id)
        .join(User, User.id == TrainingAttempt.user_id)
        .order_by(TrainingAttempt.started_at.desc())
        .limit(500)
    )
    if user_id:
        stmt = stmt.where(TrainingAttempt.user_id == user_id)
    if scenario_id:
        stmt = stmt.where(TrainingAttempt.scenario_id == scenario_id)
    if submitted_only:
        stmt = stmt.where(TrainingAttempt.submitted_at.is_not(None))
    return [_attempt_summary(a, sc, u) for a, sc, u in (await db.execute(stmt)).all()]


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def get_attempt(attempt_id: uuid.UUID, user: ResultReader, db: DB) -> dict[str, Any]:
    attempt = await db.get(TrainingAttempt, attempt_id)
    if attempt is None or (attempt.user_id != user.id and user.role not in ALL_RESULTS):
        raise AppError(404, "attempt_not_found")
    return await _attempt_out(db, attempt, user)


def _attempt_summary(a: TrainingAttempt, sc: TrainingScenario, u: User) -> dict[str, Any]:
    return {
        "id": a.id, "scenario_id": sc.id, "scenario_title_en": sc.title_en,
        "scenario_title_ur": sc.title_ur, "user_id": u.id, "user_name": u.full_name,
        "username": u.username, "started_at": a.started_at, "submitted_at": a.submitted_at,
        "score_pct": a.score_pct,
        "model_agreement_pct": (a.feedback or {}).get("model_agreement_pct"),
    }  # fmt: skip


async def _attempt_out(db: DB, attempt: TrainingAttempt, viewer: User) -> dict[str, Any]:
    sc = await svc.get_scenario(db, attempt.scenario_id)
    owner = await db.get(User, attempt.user_id)
    fb = attempt.feedback or {}
    base = _attempt_summary(attempt, sc, owner) | {
        "scenario": await _summary(db, sc, owner),
        "llm_feedback": attempt.llm_feedback,
        "llm_feedback_pending": fb.get("llm") == "pending",
        "correct_targets": fb.get("correct_targets"),
        "total_targets": fb.get("total_targets"),
    }
    if attempt.submitted_at is None:
        items = await svc.items_with_media(db, sc.id)
        return base | {"items": [svc.public_item(i, a) for i, a in items]}
    # Results: every item answered in this attempt, with ground truth and reference revealed.
    rows = (
        await db.execute(
            select(AttemptAnswer, ScenarioItem)
            .join(ScenarioItem, ScenarioItem.id == AttemptAnswer.item_id)
            .where(AttemptAnswer.attempt_id == attempt.id)
            .order_by(ScenarioItem.order, ScenarioItem.created_at)
        )
    ).all()
    items = []
    for ans, item in rows:
        asset = await db.get(MediaAsset, item.media_id)
        res = ans.per_target_results or {}
        items.append(
            svc.public_item(item, asset)
            | {
                "ground_truth": item.ground_truth,
                "reference_output": item.reference_output,
                "reference_model_version": item.reference_model_version,
                "answer": ans.answer,
                "score": res.get("score"),
                "targets": res.get("targets", []),
            }
        )
    return base | {"items": items}
