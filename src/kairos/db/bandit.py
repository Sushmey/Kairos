"""Bandit parameter store — Thompson sampling α/β per user × cluster × context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.config import settings
from kairos.db.mongo import get_database

COLLECTION = "bandit_params"
TREATMENT_COLLECTION = "bandit_treatments"
DEFAULT_ALPHA = 1.0
DEFAULT_BETA = 1.0


async def _cohort_prior(
    cluster_id: str,
    context_class: str,
    *,
    exclude_user_id: str,
) -> tuple[float, float] | None:
    """Mean α/β from other users on the same cluster×context (cold-start prior)."""
    if not settings.cohort_prior_enabled:
        return None
    pipeline = [
        {
            "$match": {
                "cluster_id": cluster_id,
                "context_class": context_class,
                "user_id": {"$ne": exclude_user_id},
            }
        },
        {
            "$group": {
                "_id": None,
                "alpha": {"$avg": "$alpha"},
                "beta": {"$avg": "$beta"},
                "users": {"$addToSet": "$user_id"},
            }
        },
    ]
    rows = await get_database()[COLLECTION].aggregate(pipeline).to_list(length=1)
    if not rows:
        return None
    row = rows[0]
    if len(row.get("users") or []) < settings.cohort_prior_min_users:
        return None
    return float(row["alpha"]), float(row["beta"])


def _apply_prior(params: dict[str, Any], prior: tuple[float, float] | None) -> dict[str, Any]:
    if prior is None:
        return params
    alpha, beta = prior
    if float(params.get("alpha", DEFAULT_ALPHA)) != DEFAULT_ALPHA or float(
        params.get("beta", DEFAULT_BETA)
    ) != DEFAULT_BETA:
        return params
    merged = dict(params)
    merged["alpha"] = alpha
    merged["beta"] = beta
    merged["cohort_prior"] = True
    return merged


def bandit_user_id(user_id: str | None = None) -> str:
    return user_id or settings.kairos_user_id or "__default__"


async def ensure_bandit_indexes() -> None:
    db = get_database()
    # Drop the pre-multi-user unique index if present — uniqueness on
    # (cluster_id, context_class) without user_id would forbid two users from
    # sharing a cluster×context pair and breaks multi-user scoping.
    try:
        existing = await db[COLLECTION].index_information()
        legacy = existing.get("cluster_id_1_context_class_1")
        if legacy and legacy.get("unique"):
            await db[COLLECTION].drop_index("cluster_id_1_context_class_1")
    except Exception:  # noqa: BLE001 — best-effort migration on fresh installs
        pass

    await db[COLLECTION].create_index(
        [("user_id", 1), ("cluster_id", 1), ("context_class", 1)],
        unique=True,
    )
    # Non-unique secondary index for legacy cross-user queries (best-effort).
    try:
        await db[COLLECTION].create_index(
            [("cluster_id", 1), ("context_class", 1)],
            name="cluster_context_lookup",
        )
    except Exception:  # noqa: BLE001
        pass


async def get_bandit_params(
    cluster_id: str,
    context_class: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return α/β for a user×cluster×context pair, creating defaults if missing."""
    uid = bandit_user_id(user_id)
    doc = await get_database()[COLLECTION].find_one(
        {"user_id": uid, "cluster_id": cluster_id, "context_class": context_class}
    )
    if doc:
        return doc
    defaults = {
        "user_id": uid,
        "cluster_id": cluster_id,
        "context_class": context_class,
        "alpha": DEFAULT_ALPHA,
        "beta": DEFAULT_BETA,
    }
    prior = await _cohort_prior(cluster_id, context_class, exclude_user_id=uid)
    return _apply_prior(defaults, prior)


async def get_bandit_params_batch(
    cluster_ids: list[str],
    context_class: str,
    *,
    user_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch bandit params for many clusters in one query."""
    if not cluster_ids:
        return {}
    uid = bandit_user_id(user_id)
    cursor = get_database()[COLLECTION].find(
        {
            "user_id": uid,
            "cluster_id": {"$in": cluster_ids},
            "context_class": context_class,
        }
    )
    docs = await cursor.to_list(length=len(cluster_ids))
    by_cluster = {doc["cluster_id"]: doc for doc in docs}
    for cluster_id in cluster_ids:
        if cluster_id in by_cluster:
            continue
        defaults = {
            "user_id": uid,
            "cluster_id": cluster_id,
            "context_class": context_class,
            "alpha": DEFAULT_ALPHA,
            "beta": DEFAULT_BETA,
        }
        prior = await _cohort_prior(cluster_id, context_class, exclude_user_id=uid)
        by_cluster[cluster_id] = _apply_prior(defaults, prior)
    return by_cluster


async def apply_bandit_reward(
    cluster_id: str,
    context_class: str,
    reward: float,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Online update — increment α on positive reward, β on negative."""
    now = datetime.now(timezone.utc)
    uid = bandit_user_id(user_id)
    alpha_delta, beta_delta = (reward, 0.0) if reward > 0 else (0.0, abs(reward))
    params = await get_bandit_params(cluster_id, context_class, user_id=uid)
    new_alpha = float(params.get("alpha", DEFAULT_ALPHA)) + alpha_delta
    new_beta = float(params.get("beta", DEFAULT_BETA)) + beta_delta
    db = get_database()
    await db[COLLECTION].update_one(
        {"user_id": uid, "cluster_id": cluster_id, "context_class": context_class},
        {
            "$set": {
                "user_id": uid,
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
        "user_id": uid,
        "cluster_id": cluster_id,
        "context_class": context_class,
        "alpha": new_alpha,
        "beta": new_beta,
    }


async def get_treatment_params(
    cluster_id: str,
    context_class: str,
    digest_style: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return α/β for a user×cluster×context×treatment tuple (GAMBITTS-lite)."""
    uid = bandit_user_id(user_id)
    doc = await get_database()[TREATMENT_COLLECTION].find_one(
        {
            "user_id": uid,
            "cluster_id": cluster_id,
            "context_class": context_class,
            "digest_style": digest_style,
        }
    )
    if doc:
        return doc
    return {
        "user_id": uid,
        "cluster_id": cluster_id,
        "context_class": context_class,
        "digest_style": digest_style,
        "alpha": DEFAULT_ALPHA,
        "beta": DEFAULT_BETA,
    }


async def apply_treatment_reward(
    cluster_id: str,
    context_class: str,
    digest_style: str,
    reward: float,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Secondary bandit update keyed on treatment (GAMBITTS-lite)."""
    now = datetime.now(timezone.utc)
    uid = bandit_user_id(user_id)
    alpha_delta, beta_delta = (reward, 0.0) if reward > 0 else (0.0, abs(reward))
    params = await get_treatment_params(cluster_id, context_class, digest_style, user_id=uid)
    new_alpha = float(params.get("alpha", DEFAULT_ALPHA)) + alpha_delta
    new_beta = float(params.get("beta", DEFAULT_BETA)) + beta_delta
    db = get_database()
    await db[TREATMENT_COLLECTION].update_one(
        {
            "user_id": uid,
            "cluster_id": cluster_id,
            "context_class": context_class,
            "digest_style": digest_style,
        },
        {
            "$set": {
                "user_id": uid,
                "cluster_id": cluster_id,
                "context_class": context_class,
                "digest_style": digest_style,
                "alpha": new_alpha,
                "beta": new_beta,
                "last_updated": now,
            }
        },
        upsert=True,
    )
    return {
        "user_id": uid,
        "cluster_id": cluster_id,
        "context_class": context_class,
        "digest_style": digest_style,
        "alpha": new_alpha,
        "beta": new_beta,
    }


async def list_bandit_params(*, limit: int = 20, user_id: str | None = None) -> list[dict[str, Any]]:
    uid = bandit_user_id(user_id)
    query: dict[str, Any] = {"user_id": uid}
    cursor = (
        get_database()[COLLECTION]
        .find(query)
        .sort([("last_updated", -1)])
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
