"""System status for admins (HANDOFF §4.3, SRS §4.8): database, models, jobs, storage,
backups, LLM and sessions, with an overall ok / warn verdict and the reasons."""

import os
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.deps import DB, require_roles
from app.events.bus import bus
from app.jobs.queue import get_queue
from app.llm.registry import get_llm
from app.ml.registry import get_models
from app.models import AnalysisJob, Incident, MediaAsset, RefreshToken, User
from app.services import settings as settings_svc
from app.storage.backend import get_storage

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[User, Depends(require_roles("admin"))]
STARTED = time.time()
BACKUP_MAX_AGE = timedelta(hours=36)  # daily job + slack
DISK_WARN_FREE = 0.10


def _backups(now: datetime) -> dict[str, Any]:
    d = Path(os.environ.get("BACKUP_DIR", "/backups"))
    if not d.is_dir():
        return {"available": False}
    dumps = sorted(d.glob("ignis-*.dump"))
    last = None
    marker = d / "LAST_BACKUP"
    if marker.exists():
        try:
            last = datetime.fromisoformat(marker.read_text().strip().replace("Z", "+00:00"))
        except ValueError:
            last = None
    return {
        "available": True,
        "count": len(dumps),
        "last_at": last,
        "latest_file": dumps[-1].name if dumps else None,
        "latest_bytes": dumps[-1].stat().st_size if dumps else None,
        "stale": last is None or now - last > BACKUP_MAX_AGE,
    }


@router.get("/status")
async def system_status(_: Admin, db: DB) -> dict[str, Any]:
    now = datetime.now(UTC)
    s = get_settings()
    warnings: list[str] = []

    t0 = time.perf_counter()
    await db.execute(text("SELECT 1"))
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    db_size = (await db.execute(text("SELECT pg_database_size(current_database())"))).scalar()
    pg_version = (await db.execute(text("SHOW server_version"))).scalar()
    revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()

    models = get_models()
    if models.fallback_reason:
        warnings.append("ml_fallback")

    jobs = dict(
        (await db.execute(select(AnalysisJob.status, func.count()).group_by(AnalysisJob.status)))
        .tuples()
        .all()
    )
    failed_24h = (
        await db.execute(
            select(func.count()).where(
                AnalysisJob.status == "failed", AnalysisJob.finished_at > now - timedelta(days=1)
            )
        )
    ).scalar_one()
    if failed_24h:
        warnings.append("jobs_failed")
    queue = get_queue()

    root = get_storage().root  # type: ignore[attr-defined]
    usage = shutil.disk_usage(root) if Path(root).exists() else None
    media_count, media_bytes = (
        await db.execute(select(func.count(), func.coalesce(func.sum(MediaAsset.bytes), 0)))
    ).one()
    if usage and usage.free / usage.total < DISK_WARN_FREE:
        warnings.append("disk_low")

    backups = _backups(now)
    if not backups["available"]:
        warnings.append("backups_not_visible")
    elif backups["stale"]:
        warnings.append("backup_stale")

    flags = (await settings_svc.load_all(db))["llm.features"]
    llm = get_llm()
    llm_wanted = s.llm_provider != "template"
    if llm_wanted and llm.name == "template":
        warnings.append("llm_key_missing")

    roles = dict(
        (
            await db.execute(
                select(User.role, func.count()).where(User.is_active.is_(True)).group_by(User.role)
            )
        )
        .tuples()
        .all()
    )
    sessions = (
        await db.execute(
            select(func.count()).where(
                RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now
            )
        )
    ).scalar_one()
    open_incidents = (
        await db.execute(
            select(func.count()).where(
                Incident.status.in_(("dispatched", "active")), Incident.deleted_at.is_(None)
            )
        )
    ).scalar_one()

    return {
        "status": "warn" if warnings else "ok",
        "warnings": warnings,
        "checked_at": now,
        "app": {
            "version": s.version,
            "environment": s.environment,
            "uptime_s": int(time.time() - STARTED),
        },
        "database": {
            "ok": True,
            "latency_ms": latency_ms,
            "size_bytes": db_size,
            "server_version": pg_version,
            "migration": revision,
        },
        "ml": {
            "backend": models.backend,
            "device": os.environ.get("ML_DEVICE", "cpu"),
            "models": models.versions(),
            "fallback_reason": models.fallback_reason,
            "mock_scenario": (
                os.environ.get("MOCK_SCENARIO", "calm") if models.backend == "mock" else None
            ),
        },
        "jobs": {
            "by_status": {k: jobs.get(k, 0) for k in ("queued", "running", "done", "failed")},
            "failed_24h": failed_24h,
            "queue_depth": queue.depth(),
            "workers": queue.workers,
        },
        "storage": {
            "media_files": media_count,
            "media_bytes": int(media_bytes),
            "disk_total": usage.total if usage else None,
            "disk_free": usage.free if usage else None,
        },
        "backups": backups,
        "llm": {
            "provider": s.llm_provider,
            "active": llm.name != "template",
            "model": s.llm_model if llm_wanted else None,
            "features": flags,
        },
        "users": {"active_by_role": roles, "active_sessions": sessions},
        "live": {"open_incidents": open_incidents, "live_connections": bus.subscriber_count()},
    }
