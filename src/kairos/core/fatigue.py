"""Fatigue field helpers — daily budget and min-gap between surfaces."""

from __future__ import annotations

from datetime import datetime, timezone

from kairos.models.schemas import ContextSnapshot


def refresh_fatigue_fields(context: ContextSnapshot) -> ContextSnapshot:
    """Refresh timers before a heartbeat decision."""
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    updates: dict = {}

    if context.surface_budget_day != today:
        updates["surfaces_today"] = 0
        updates["surface_budget_day"] = today

    if context.last_surface_at:
        elapsed = int((now - context.last_surface_at).total_seconds() // 60)
        updates["time_since_last_surface_minutes"] = max(0, elapsed)

    if not updates:
        return context
    return context.model_copy(update=updates)


def apply_surface_fatigue(context: ContextSnapshot) -> ContextSnapshot:
    """Update fatigue counters after a successful SURFACE."""
    now = datetime.now(timezone.utc)
    return context.model_copy(
        update={
            "surfaces_today": context.surfaces_today + 1,
            "time_since_last_surface_minutes": 0,
            "last_surface_at": now,
            "surface_budget_day": now.date().isoformat(),
        }
    )
