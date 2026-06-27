"""Bandit parameter store — Thompson sampling α/β per cluster × context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database

COLLECTION = "bandit_params"
DEFAULT_ALPHA = 1.0
DEFAULT_BETA = 1.0


async def ensure_bandit_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index(
        [("cluster_id", 1), ("context_class", 1)],
        unique=True,
    )


async def get_bandit_params(cluster_id: str, context_class: str) -> dict[str, Any]:
    """Return α/β for a cluster×context pair, creating defaults if missing."""
    doc = await get_database()[COLLECTION].find_one(
        {"cluster_id": cluster_id, "context_class": context_class}
    )
    if doc:
        return doc
    return {
        "cluster_id": cluster_id,
        "context_class": context_class,
        "alpha": DEFAULT_ALPHA,
        "beta": DEFAULT_BETA,
    }


async def apply_bandit_reward(
    cluster_id: str,
    context_class: str,
    reward: float,
) -> dict[str, Any]:
    """Online update — increment α on positive reward, β on negative."""
    now = datetime.now(timezone.utc)
    alpha_delta, beta_delta = (reward, 0.0) if reward > 0 else (0.0, abs(reward))
    params = await get_bandit_params(cluster_id, context_class)
    new_alpha = float(params.get("alpha", DEFAULT_ALPHA)) + alpha_delta
    new_beta = float(params.get("beta", DEFAULT_BETA)) + beta_delta
    db = get_database()
    await db[COLLECTION].update_one(
        {"cluster_id": cluster_id, "context_class": context_class},
        {
            "$set": {
                "cluster_id": cluster_id,
                "context_class": context_class,
                "alpha": new_alpha,
                "beta": new_beta,
                "last_updated": now,
            }
        },
        upsert=True,
    )
    return {
        "cluster_id": cluster_id,
        "context_class": context_class,
        "alpha": new_alpha,
        "beta": new_beta,
    }


async def list_bandit_params(*, limit: int = 20) -> list[dict[str, Any]]:
    cursor = (
        get_database()[COLLECTION]
        .find({})
        .sort([("last_updated", -1)])
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
