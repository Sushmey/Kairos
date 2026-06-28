"""Persisted pipeline events — shared log for SSE across processes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from kairos.config import settings
from kairos.db.mongo import get_database
from kairos.observability.bus import AgentEvent

COLLECTION = "pipeline_events"


async def ensure_event_indexes() -> None:
    db = get_database()
    ttl_seconds = max(1, settings.event_persist_ttl_days) * 86400
    await db[COLLECTION].create_index(
        "timestamp",
        expireAfterSeconds=ttl_seconds,
    )


async def insert_pipeline_event(event: AgentEvent) -> None:
    if not settings.event_persist_enabled:
        return
    await ensure_event_indexes()
    payload = {
        "timestamp": event.timestamp,
        "kind": event.kind,
        "message": event.message,
        "data": event.data,
    }
    await get_database()[COLLECTION].insert_one(payload)


async def list_recent_events(*, limit: int = 500) -> list[AgentEvent]:
    if not settings.event_persist_enabled:
        return []
    await ensure_event_indexes()
    since = datetime.now(timezone.utc) - timedelta(days=settings.event_persist_ttl_days)
    cursor = (
        get_database()[COLLECTION]
        .find({"timestamp": {"$gte": since}})
        .sort([("timestamp", 1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    events: list[AgentEvent] = []
    for doc in docs:
        ts = doc.get("timestamp")
        if ts and getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc)
        events.append(
            AgentEvent(
                timestamp=ts or datetime.now(timezone.utc),
                kind=str(doc.get("kind") or "unknown"),
                message=str(doc.get("message") or ""),
                data=dict(doc.get("data") or {}),
            )
        )
    return events
