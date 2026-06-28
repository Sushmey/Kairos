"""Persisted ingest cursors and sync metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database

COLLECTION = "sync_state"


async def get_sync_state(source: str = "x_bookmarks") -> dict[str, Any]:
    doc = await get_database()[COLLECTION].find_one({"source": source})
    if not doc:
        return {"source": source, "last_sync_at": None, "last_pages": 0, "last_fetched": 0}
    doc.pop("_id", None)
    return doc


async def update_sync_state(
    source: str,
    *,
    pages: int,
    fetched: int,
    incremental: bool,
    stopped_early: bool,
    stop_reason: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    await get_database()[COLLECTION].update_one(
        {"source": source},
        {
            "$set": {
                "source": source,
                "last_sync_at": now,
                "last_pages": pages,
                "last_fetched": fetched,
                "last_incremental": incremental,
                "last_stopped_early": stopped_early,
                "last_stop_reason": stop_reason,
                "updated_at": now,
            }
        },
        upsert=True,
    )
