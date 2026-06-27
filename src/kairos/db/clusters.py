"""Cluster repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database

COLLECTION = "clusters"


async def ensure_cluster_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("cluster_id", unique=True)


async def replace_all_clusters(clusters: list[dict[str, Any]]) -> int:
    """Replace cluster catalog with a fresh HDBSCAN pass."""
    db = get_database()
    await db[COLLECTION].delete_many({})
    if not clusters:
        return 0
    await db[COLLECTION].insert_many(clusters)
    return len(clusters)


async def list_clusters(*, limit: int = 50) -> list[dict[str, Any]]:
    cursor = (
        get_database()[COLLECTION]
        .find({})
        .sort([("member_count", -1), ("name", 1)])
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
