"""Web delivery — SSE + notification inbox events."""

from __future__ import annotations

from kairos.models.schemas import HeartbeatResult, NotificationRecord
from kairos.observability.bus import event_bus


class WebDeliveryAdapter:
    name = "web"

    async def deliver(self, result: HeartbeatResult, notification: NotificationRecord) -> None:
        cluster = notification.digest.cluster_name if notification.digest else "cluster"
        links = len(notification.digest.links) if notification.digest else 0
        event_bus.emit(
            "notification",
            f"Pushed «{cluster}» digest to the web inbox ({links} links).",
            notification_id=notification.notification_id,
            digest=notification.digest.model_dump() if notification.digest else None,
            delivery=result.delivery.model_dump() if result.delivery else None,
        )
