"""Feedback event persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from kairos.config import settings
from kairos.db.bandit import bandit_user_id
from kairos.db.mongo import get_database
from kairos.models.schemas import ContextSnapshot, FeedbackAction

COLLECTION = "feedback_events"


async def ensure_feedback_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("notification_id")
    await db[COLLECTION].create_index([("context_class", 1), ("created_at", -1)])
    await db[COLLECTION].create_index([("cluster_id", 1), ("created_at", -1)])
    await db[COLLECTION].create_index(
        [("user_id", 1), ("context_class", 1), ("created_at", -1)]
    )


async def insert_feedback_event(
    *,
    notification_id: str,
    cluster_id: str,
    context_class: str,
    context_snapshot: ContextSnapshot,
    action: FeedbackAction,
    derived_reward: float | None,
    notification_text: str,
    url: str | None = None,
    user_id: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    event_id = str(uuid4())
    events: list[dict[str, Any]] = [{"type": "shown", "t": 0}]
    payload: dict[str, Any] = {"type": action, "t": 0}
    if url:
        payload["url"] = url
    events.append(payload)

    doc = {
        "event_id": event_id,
        "notification_id": notification_id,
        "user_id": bandit_user_id(user_id),
        "cluster_id": cluster_id,
        "context_class": context_class,
        "context_snapshot": context_snapshot.model_dump(),
        "notification_text": notification_text,
        "events": events,
        "derived_reward": derived_reward,
        "snooze_context": context_snapshot.model_dump() if action == "snoozed" else None,
        "created_at": now,
    }
    await get_database()[COLLECTION].insert_one(doc)
    return event_id


async def list_snoozed_cluster_ids(
    context_class: str,
    *,
    user_id: str | None = None,
) -> list[str]:
    """Cluster IDs snoozed for this user × context bucket within the TTL window."""
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.snooze_ttl_minutes)
    uid = bandit_user_id(user_id)
    cursor = get_database()[COLLECTION].find(
        {
            "user_id": uid,
            "context_class": context_class,
            "events": {"$elemMatch": {"type": "snoozed"}},
            "created_at": {"$gte": since},
        },
        {"cluster_id": 1},
    )
    docs = await cursor.to_list(length=100)
    return list({doc["cluster_id"] for doc in docs if doc.get("cluster_id")})
