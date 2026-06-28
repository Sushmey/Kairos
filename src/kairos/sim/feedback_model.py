"""Deterministic feedback model — maps persona × cluster × context → FeedbackAction."""

from __future__ import annotations

import random

from kairos.models.schemas import ContextSnapshot, FeedbackAction
from kairos.sim.persona import Persona, topic_fit


def simulate_feedback(
    persona: Persona,
    cluster_name: str,
    context: ContextSnapshot,
    hour: int,
    seed: int = 0,
) -> FeedbackAction:
    """Return a FeedbackAction a persona would take given this surface."""
    rng = random.Random(seed)

    fit = topic_fit(persona, cluster_name)
    capacity = min(1.0, context.calendar_gap_minutes / 60.0)

    # Hour-of-day factor
    start, end = persona.active_hours
    if start <= hour < end:
        hour_factor = 1.0
    else:
        hour_factor = 0.2  # outside active hours → almost always ignored

    # Deep-work penalty — rarely interrupt during focused blocks
    in_deep_work = any(s <= hour < e for s, e in persona.deep_work_blocks)
    deep_factor = 0.3 if in_deep_work else 1.0

    base = fit * capacity * hour_factor * deep_factor
    noise = rng.gauss(0, 0.12)
    score = max(0.0, min(1.0, base + noise))

    # Style overrides
    if persona.engagement_style == "snoozer":
        if context.meeting_density_today > 0.6 and score < 0.65:
            return "snoozed"
    elif persona.engagement_style == "dismissive":
        # Jordan dismisses unless the fit is very strong
        if score < 0.55:
            return "dismissed"

    # Score → action
    if score >= 0.75:
        return "link_click"
    if score >= 0.50:
        return "expanded"
    if score >= 0.28:
        return "dismissed"
    return "ignored"
