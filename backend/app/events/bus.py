"""In-process pub/sub for live events (HANDOFF §2). Swap for a Redis implementation behind
the same interface when running more than one backend process."""

import asyncio
import contextlib
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any, Protocol

log = logging.getLogger(__name__)

STATION = "station"


def incident_channel(incident_id: Any) -> str:
    return f"incident:{incident_id}"


class EventBus(Protocol):
    async def publish(self, channel: str, event: dict[str, Any]) -> None: ...
    def subscribe(self, channel: str) -> contextlib.AbstractAsyncContextManager[AsyncIterator]: ...
    def subscriber_count(self) -> int: ...


class InMemoryEventBus:
    """Fan-out to per-subscriber bounded queues. A slow subscriber drops its oldest events
    rather than blocking publishers (clients refetch the aggregate on reconnect anyway)."""

    def __init__(self, queue_size: int = 256) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._size = queue_size

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        for q in list(self._subs.get(channel, ())):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            q.put_nowait(event)

    @contextlib.asynccontextmanager
    async def subscribe(self, channel: str):
        q: asyncio.Queue = asyncio.Queue(self._size)
        self._subs[channel].add(q)

        async def _iter():
            while True:
                yield await q.get()

        try:
            yield _iter()
        finally:
            self._subs[channel].discard(q)
            if not self._subs[channel]:
                self._subs.pop(channel, None)

    def subscriber_count(self) -> int:
        return sum(len(s) for s in self._subs.values())


bus: EventBus = InMemoryEventBus()
