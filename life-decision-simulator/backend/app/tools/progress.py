from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# One asyncio Queue per active session — lives only while SSE connection is open
_queues: dict[str, asyncio.Queue] = {}


def create_queue(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = q
    return q


def remove_queue(session_id: str) -> None:
    _queues.pop(session_id, None)


async def emit(session_id: str, message: str, step: Optional[int] = None) -> None:
    """Push a progress event. Silently no-ops if no SSE client is connected."""
    q = _queues.get(session_id)
    if q:
        await q.put({"message": message, "step": step})


async def done(session_id: str) -> None:
    """Signal that the analysis is complete."""
    q = _queues.get(session_id)
    if q:
        await q.put(None)  # sentinel — SSE generator stops on None
