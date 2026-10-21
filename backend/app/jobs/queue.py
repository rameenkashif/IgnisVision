"""Background analysis jobs (HANDOFF §2): an in-process asyncio queue backed by the
analysis_jobs table, behind a JobQueue interface so Redis/RQ/Celery can replace it."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

from sqlalchemy import select

from app.db.engine import SessionLocal
from app.models import AnalysisJob

log = logging.getLogger(__name__)
Handler = Callable[[uuid.UUID], Awaitable[None]]


class JobQueue(Protocol):
    async def enqueue(self, job_id: uuid.UUID) -> None: ...
    async def resume_pending(self) -> int: ...
    async def shutdown(self) -> None: ...
    def depth(self) -> int: ...


class InProcessJobQueue:
    def __init__(self, handlers: dict[str, Handler], workers: int = 2):
        self.handlers = handlers
        self.workers = workers
        self._queue: asyncio.Queue[uuid.UUID] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: list[asyncio.Task] = []
        self.running = 0

    def _ensure(self) -> asyncio.Queue:
        loop = asyncio.get_running_loop()
        if self._queue is None or self._loop is not loop:  # new loop (tests, restarts)
            self._loop, self._queue = loop, asyncio.Queue()
            self._tasks = [loop.create_task(self._worker()) for _ in range(self.workers)]
        return self._queue

    async def enqueue(self, job_id: uuid.UUID) -> None:
        self._ensure().put_nowait(job_id)

    async def resume_pending(self) -> int:
        """After a restart, re-run jobs that were queued or interrupted mid-run."""
        async with SessionLocal() as db:
            ids = (
                (
                    await db.execute(
                        select(AnalysisJob.id)
                        .where(AnalysisJob.status.in_(("queued", "running")))
                        .order_by(AnalysisJob.created_at)
                    )
                )
                .scalars()
                .all()
            )
        for job_id in ids:
            await self.enqueue(job_id)
        return len(ids)

    def depth(self) -> int:
        return (self._queue.qsize() if self._queue else 0) + self.running

    async def shutdown(self) -> None:
        """Stop workers (app shutdown / end of a test loop). Unfinished jobs stay in the DB as
        queued/running and are resumed on the next start."""
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except BaseException:  # noqa: BLE001,S110  (cancelled)
                pass
        self._tasks, self._queue, self._loop = [], None, None

    async def _worker(self) -> None:
        assert self._queue is not None
        while True:
            job_id = await self._queue.get()
            self.running += 1
            try:
                async with SessionLocal() as db:
                    job = await db.get(AnalysisJob, job_id)
                    handler = self.handlers.get(job.job_type) if job else None
                if handler is None:
                    log.error("no handler for job %s", job_id)
                else:
                    await handler(job_id)
            except Exception:
                log.exception("job %s crashed", job_id)
            finally:
                self.running -= 1
                self._queue.task_done()


_queue: InProcessJobQueue | None = None


def get_queue() -> InProcessJobQueue:
    global _queue
    if _queue is None:
        from app.jobs.thermal_pose_job import run_thermal_pose_job

        _queue = InProcessJobQueue({"thermal_pose": run_thermal_pose_job})
    return _queue
