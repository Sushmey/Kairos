"""Delivery adapter protocol."""

from __future__ import annotations

from typing import Protocol

from kairos.models.schemas import HeartbeatResult, NotificationRecord


class DeliveryAdapter(Protocol):
    name: str

    async def deliver(self, result: HeartbeatResult, notification: NotificationRecord) -> None:
        """Fan out a surface event to this channel."""
        ...
