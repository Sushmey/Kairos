"""Store GEPA optimization run results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database

COLLECTION = "optimization_runs"


async def save_optimization_run(
    prompt_before: str,
    prompt_after: str,
    engagement_before: float,
    engagement_after: float,
    diff_summary: str,
    sample_count: int = 0,
) -> str:
    """Persist a GEPA optimization run and return its id."""
    doc: dict[str, Any] = {
        "run_at": datetime.now(timezone.utc),
        "prompt_before": prompt_before,
        "prompt_after": prompt_after,
        "engagement_before": round(engagement_before, 4),
        "engagement_after": round(engagement_after, 4),
        "engagement_delta": round(engagement_after - engagement_before, 4),
        "diff_summary": diff_summary,
        "sample_count": sample_count,
    }
    result = await get_database()[COLLECTION].insert_one(doc)
    return str(result.inserted_id)


async def get_active_prompt() -> str | None:
    """Return the most recent optimized digest prompt, or None to use the default."""
    doc = await get_database()[COLLECTION].find_one(
        {"engagement_delta": {"$gt": 0}},
        sort=[("run_at", -1)],
    )
    return doc["prompt_after"] if doc else None


async def list_optimization_runs(limit: int = 10) -> list[dict[str, Any]]:
    cursor = (
        get_database()[COLLECTION]
        .find({})
        .sort([("run_at", -1)])
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    for row in rows:
        row["id"] = str(row.pop("_id", ""))
        if row.get("run_at") and hasattr(row["run_at"], "isoformat"):
            row["run_at"] = row["run_at"].isoformat()
    return rows
