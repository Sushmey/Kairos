"""Demo helpers — shared reset + surface for scripts and web API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.core.context import get_context_async, write_context
from kairos.models.schemas import ContextSnapshot

DEFAULT_DEMO_OVERRIDE = (
    "42 minute gap before architecture review — deep focus window, "
    "pre-meeting prep time, distributed systems study"
)


async def reset_demo_headspace(*, user_id: str | None = None) -> ContextSnapshot:
    """Clear fatigue gates and set stage-friendly headspace for a reliable SURFACE."""
    ctx = await get_context_async(user_id)
    now = datetime.now(timezone.utc)
    past_surface = now - timedelta(hours=3)
    sources = [s for s in ctx.sensor_sources if s != "demo_stub"] or ["demo_reset"]
    updated = ctx.model_copy(
        update={
            "calendar_gap_minutes": 90,
            "surfaces_today": 0,
            "time_since_last_surface_minutes": 180,
            "last_surface_at": past_surface,
            "surface_budget_day": now.date().isoformat(),
            "location_type": "cafe",
            "upcoming_event_title": "Architecture review",
            "attention_capacity": "high",
            "topical_affinity": "work",
            "sensor_sources": sources,
            "moment_narrative": None,
            "moment_narrative_at": None,
        }
    )
    await write_context(updated, user_id=user_id)
    return updated
