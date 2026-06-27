"""Compose headspace moment text and context buckets for ranking."""

from __future__ import annotations

from kairos.models.schemas import ContextSnapshot


def context_class(context: ContextSnapshot) -> str:
    """Bucket context for bandit_params lookup."""
    gap = "long_gap" if context.calendar_gap_minutes >= 60 else "short_gap"
    return f"{context.location_type}_{gap}"


def moment_text(context: ContextSnapshot, override: str | None = None) -> str:
    """Natural-language headspace string embedded as the query vector."""
    if override:
        return override.strip()

    parts: list[str] = []
    if context.upcoming_event_title:
        parts.append(f"Upcoming: {context.upcoming_event_title}")
    if context.recent_event_title:
        parts.append(f"Just finished: {context.recent_event_title}")
    parts.append(f"Location: {context.location_type}")
    parts.append(f"Calendar gap: {context.calendar_gap_minutes} minutes")
    if context.post_meeting_minutes is not None:
        parts.append(f"Post-meeting: {context.post_meeting_minutes} min")
    parts.append(f"Meeting density today: {context.meeting_density_today:.1f}")
    return ". ".join(parts)
