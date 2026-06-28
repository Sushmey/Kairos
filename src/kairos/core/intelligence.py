"""Gemini intelligence layer — enriches context before policy runs."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from kairos.config import settings
from kairos.core.context import is_demo_context
from kairos.core.headspace import fuse_headspace
from kairos.models.schemas import ContextSnapshot, LocationType
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)


def narrative_is_fresh(context: ContextSnapshot) -> bool:
    if not context.moment_narrative:
        return False
    if not context.moment_narrative_at:
        return True
    age = (datetime.now(timezone.utc) - context.moment_narrative_at).total_seconds()
    return age < settings.intelligence_narrative_ttl_seconds


async def prepare_context_for_decision(context: ContextSnapshot) -> ContextSnapshot:
    """Ensure context has LLM moment narrative before ranking (cached by TTL)."""
    if not settings.intelligence_headspace_enabled:
        return context
    if settings.intelligence_skip_demo_narrative and is_demo_context(context):
        return context
    if narrative_is_fresh(context):
        return context
    return await asyncio.to_thread(_enrich_narrative_sync, context)


def _enrich_narrative_sync(context: ContextSnapshot) -> ContextSnapshot:
    from kairos.llm.compose import enrich_context_narrative

    try:
        return enrich_context_narrative(context)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Headspace narrative enrichment failed: %s", exc)
        event_bus.emit("intelligence", f"Headspace enrichment failed — {exc}", error=str(exc))
        return context


def fuse_headspace_intelligent(
    *,
    calendar_events: list[dict[str, Any]] | None = None,
    email_threads: list[dict[str, Any]] | None = None,
    email_themes: list[str] | None = None,
    location_type: LocationType | None = None,
    lat: float | None = None,
    lng: float | None = None,
    surfaces_today: int | None = None,
    time_since_last_surface_minutes: int | None = None,
    sensor_sources: list[str] | None = None,
    **overrides: Any,
) -> ContextSnapshot:
    """Heuristic fuse (numeric calendar) + LLM enrichment (interpretive fields)."""
    base = fuse_headspace(
        calendar_events=calendar_events,
        email_threads=email_threads,
        email_themes=email_themes,
        location_type=location_type,
        lat=lat,
        lng=lng,
        surfaces_today=surfaces_today,
        time_since_last_surface_minutes=time_since_last_surface_minutes,
        sensor_sources=sensor_sources,
        **overrides,
    )
    if not settings.intelligence_headspace_enabled:
        return base
    if not calendar_events and not email_threads:
        return base

    from kairos.llm.compose import enrich_headspace_from_sensors

    try:
        return enrich_headspace_from_sensors(
            base,
            calendar_events=calendar_events,
            email_threads=email_threads,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM headspace fusion failed, using heuristics: %s", exc)
        event_bus.emit(
            "intelligence",
            f"Sensor fusion fell back to heuristics — {exc}",
            error=str(exc),
        )
        return base
