from __future__ import annotations

import asyncio
import time
from typing import Any

DEFAULT_EVENT = {"drop_id": "", "status": "", "message": "", "ts": ""}


class EventManager:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._queues.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        for queue in list(self._queues):
            await queue.put(event)


event_manager = EventManager()
