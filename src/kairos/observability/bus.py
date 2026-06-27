"""In-process event bus for SSE dashboard observability."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentEvent:
    timestamp: datetime
    kind: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        import json

        payload = {
            "timestamp": self.timestamp.isoformat(),
            "kind": self.kind,
            "message": self.message,
            "data": self.data,
        }
        return f"data: {json.dumps(payload)}\n\n"


class EventBus:
    """Thread-safe async pub/sub for agent activity streaming."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []
        self._history: list[AgentEvent] = []
        self._max_history = 500

    def emit(self, kind: str, message: str, **data: Any) -> AgentEvent:
        event = AgentEvent(
            timestamp=datetime.now(timezone.utc),
            kind=kind,
            message=message,
            data=data,
        )
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def subscribe(self) -> asyncio.Queue[AgentEvent]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[AgentEvent]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def history(self) -> list[AgentEvent]:
        return list(self._history)

    async def stream(self) -> AsyncIterator[AgentEvent]:
        queue = self.subscribe()
        try:
            for past in self._history:
                yield past
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(queue)


# Module-level singleton for FastAPI SSE wiring later
event_bus = EventBus()
