"""Inference never blocks the event loop (HANDOFF §7.3): models run in a bounded thread pool."""

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")

_pool = ThreadPoolExecutor(
    max_workers=int(os.environ.get("ML_WORKERS", "4")), thread_name_prefix="ml"
)


async def run(fn: Callable[..., T], *args) -> T:
    return await asyncio.get_running_loop().run_in_executor(_pool, fn, *args)
