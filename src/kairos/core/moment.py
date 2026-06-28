"""Compose headspace moment text and context buckets for ranking."""

from __future__ import annotations

from kairos.models.schemas import ContextSnapshot


def context_class(context: ContextSnapshot) -> str:
    """Bucket context for bandit_params lookup."""
    gap = "long_gap" if context.calendar_gap_minutes >= 60 else "short_gap"
    base = f"{context.location_type}_{gap}"
    if context.topical_affinity:
        return f"{base}_{context.topical_affinity}"
    return base


def moment_text(context: ContextSnapshot, override: str | None = None) -> str:
    """Natural-language headspace string embedded as the query vector."""
    if override:
        return override.strip()
    if context.moment_narrative:
        return context.moment_narrative.strip()

    parts: list[str] = []
    if context.topical_affinity:
        parts.append(f"Headspace mode: {context.topical_affinity}")
    if context.upcoming_event_title:
        parts.append(f"Upcoming: {context.upcoming_event_title}")
    if context.recent_event_title:
        parts.append(f"Just finished: {context.recent_event_title}")
    if context.email_themes:
        parts.append(f"Recent email themes: {', '.join(context.email_themes[:5])}")
    parts.append(f"Location: {context.location_type}")
    parts.append(f"Calendar gap: {context.calendar_gap_minutes} minutes")
    if context.post_meeting_minutes is not None:
        parts.append(f"Post-meeting: {context.post_meeting_minutes} min")
    if context.communication_burst:
        parts.append("Communication processing window after meeting")
    if context.attention_capacity:
        parts.append(f"Attention capacity: {context.attention_capacity}")
    parts.append(f"Meeting density today: {context.meeting_density_today:.1f}")
    return ". ".join(parts)
