"""Recompute every trainer reference output with the currently configured models.

Run after a model update (docs/MODEL_INTEGRATION.md):
    docker compose exec backend python -m app.db.recompute_references
"""

import asyncio
import sys

from sqlalchemy import select

from app.db.engine import SessionLocal, engine
from app.ml.registry import load_models
from app.models import ScenarioItem
from app.services.training import compute_reference


async def main() -> int:
    models = load_models()
    done = skipped = failed = 0
    async with SessionLocal() as db:
        for item in (await db.execute(select(ScenarioItem))).scalars().all():
            try:
                if await compute_reference(db, item):
                    done += 1
                else:
                    skipped += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"item {item.id}: {e!r}", file=sys.stderr)
        await db.commit()
    await engine.dispose()
    print(f"Models: {models.backend} {models.versions()}")
    print(f"Reference outputs: {done} computed, {skipped} without targets, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
