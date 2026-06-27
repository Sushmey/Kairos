"""Notification persistence — in-memory stub until MongoDB is wired."""

from __future__ import annotations

from kairos.models.schemas import NotificationRecord, SurfaceDecision

_store: dict[str, NotificationRecord] = {}


def save_notification(decision: SurfaceDecision) -> NotificationRecord:
    """Persist a surface event. Returns the canonical notification record."""
    record = NotificationRecord(
        cluster_id=decision.cluster_id,
        digest=decision.digest,
        context_snapshot=decision.context,
    )
    _store[record.notification_id] = record
    # TODO: upsert to MongoDB notifications collection
    return record


def get_notification(notification_id: str) -> NotificationRecord | None:
    return _store.get(notification_id)
