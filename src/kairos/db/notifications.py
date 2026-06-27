"""Notification persistence in MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database
from kairos.models.schemas import NotificationRecord, NotificationStatus, SurfaceDecision

COLLECTION = "notifications"


async def ensure_notification_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("notification_id", unique=True)
    await db[COLLECTION].create_index("created_at")


async def save_notification(decision: SurfaceDecision) -> NotificationRecord:
    """Persist a surface event."""
    await ensure_notification_indexes()
    record = NotificationRecord(
        cluster_id=decision.cluster_id,
        digest=decision.digest,
        context_snapshot=decision.context,
    )
    payload = record.model_dump(mode="json")
    await get_database()[COLLECTION].insert_one(payload)
    return record


async def get_notification(notification_id: str) -> NotificationRecord | None:
    doc = await get_database()[COLLECTION].find_one({"notification_id": notification_id})
    if not doc:
        return None
    doc.pop("_id", None)
    return NotificationRecord.model_validate(doc)


async def update_notification_status(
    notification_id: str,
    status: NotificationStatus,
) -> bool:
    result = await get_database()[COLLECTION].update_one(
        {"notification_id": notification_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count > 0


async def list_notifications(*, limit: int = 20) -> list[dict[str, Any]]:
    cursor = (
        get_database()[COLLECTION]
        .find({})
        .sort([("created_at", -1)])
        .limit(limit)
    )
    return await cursor.to_list(length=limit)
