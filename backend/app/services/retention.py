"""Data retention (DECISIONS Q14): when `retention_days` is set, closed or deleted incidents
older than that are removed with all their data and media files. Open incidents are never
touched. Off by default. Runs hourly in the backend and on demand:
    docker compose exec backend python -m app.services.retention [--dry-run]
"""

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import SessionLocal
from app.models import Incident, MediaAsset
from app.services import audit
from app.services import settings as settings_svc
from app.services.video import frames_prefix
from app.storage.backend import get_storage

log = logging.getLogger(__name__)
INTERVAL_S = int(os.environ.get("RETENTION_INTERVAL_S", "3600"))


@dataclass
class PurgeResult:
    enabled: bool
    cutoff: datetime | None = None
    incidents: list[str] = field(default_factory=list)  # codes
    files: int = 0


async def purge(
    db: AsyncSession, now: datetime | None = None, dry_run: bool = False
) -> PurgeResult:
    days = (await settings_svc.load_all(db))["retention_days"]
    if not days:
        return PurgeResult(enabled=False)
    cutoff = (now or datetime.now(UTC)) - timedelta(days=int(days))
    rows = (
        await db.execute(
            select(Incident.id, Incident.code).where(
                or_(
                    and_(Incident.status == "closed", Incident.closed_at < cutoff),
                    Incident.deleted_at < cutoff,
                )
            )
        )
    ).all()
    result = PurgeResult(enabled=True, cutoff=cutoff, incidents=sorted(c for _, c in rows))
    if not rows or dry_run:
        return result
    ids = [i for i, _ in rows]
    keys = (
        (await db.execute(select(MediaAsset.storage_key).where(MediaAsset.incident_id.in_(ids))))
        .scalars()
        .all()
    )
    await db.execute(delete(Incident).where(Incident.id.in_(ids)))  # children cascade
    await audit.record(
        db,
        actor_id=None,
        action="retention.purge",
        entity_type="incident",
        before={"incidents": result.incidents, "media_files": len(keys)},
        after={"retention_days": int(days), "cutoff": cutoff.isoformat()},
    )
    await db.commit()
    storage = get_storage()
    for key in keys:  # after the commit: a failed delete leaves an orphan file, not a dangling row
        try:
            storage.delete(key)
            storage.delete_tree(frames_prefix(key))
        except (OSError, ValueError):
            log.warning("retention: could not delete %s", key)
    result.files = len(keys)
    log.info("retention: removed %d incidents and %d media files", len(ids), len(keys))
    return result


async def run_forever() -> None:
    """Background loop started with the app; a failure is logged and retried next hour."""
    await asyncio.sleep(60)
    while True:
        try:
            async with SessionLocal() as db:
                await purge(db)
        except Exception:  # noqa: BLE001
            log.exception("retention run failed")
        await asyncio.sleep(INTERVAL_S)


async def _main(dry_run: bool) -> None:
    async with SessionLocal() as db:
        r = await purge(db, dry_run=dry_run)
    if not r.enabled:
        print("Retention is off (Administration → System settings → Data retention).")
        return
    verb = "Would remove" if dry_run else "Removed"
    print(f"{verb} {len(r.incidents)} incidents closed or deleted before {r.cutoff:%Y-%m-%d}: "
          f"{', '.join(r.incidents) or '—'}")  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply the data-retention setting now.")
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(_main(parser.parse_args().dry_run))
