"""Resolve and invoke delivery adapters."""

from __future__ import annotations

from kairos.config import settings
from kairos.delivery.base import DeliveryAdapter
from kairos.delivery.os import OSDeliveryAdapter
from kairos.delivery.web import WebDeliveryAdapter
from kairos.models.schemas import DeliveryMode, HeartbeatResult, NotificationRecord

_ADAPTERS: dict[str, DeliveryAdapter] = {
    "web": WebDeliveryAdapter(),
    "os": OSDeliveryAdapter(),
}


def resolve_adapters(mode: DeliveryMode) -> list[DeliveryAdapter]:
    """Return adapters to invoke for this heartbeat run."""
    if mode == "return_only" or mode == "none":
        return []

    targets = settings.delivery_target_list()
    adapters: list[DeliveryAdapter] = []

    if "web" in targets:
        adapters.append(_ADAPTERS["web"])
    if "os" in targets and settings.os_delivery_enabled:
        adapters.append(_ADAPTERS["os"])

    return adapters


async def deliver(
    result: HeartbeatResult,
    notification: NotificationRecord,
    mode: DeliveryMode,
) -> None:
    for adapter in resolve_adapters(mode):
        await adapter.deliver(result, notification)
