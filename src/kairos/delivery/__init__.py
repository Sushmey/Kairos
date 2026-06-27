"""Delivery adapters — web SSE, OS notify, host hints."""

from kairos.delivery.registry import deliver, resolve_adapters

__all__ = ["deliver", "resolve_adapters"]
