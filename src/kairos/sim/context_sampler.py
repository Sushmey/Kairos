"""Sample realistic ContextSnapshots for a given persona, day, and tick."""

from __future__ import annotations

import random
from typing import Literal

from kairos.core.headspace import infer_attention_capacity, infer_topical_affinity
from kairos.models.schemas import ContextSnapshot
from kairos.sim.persona import Persona

# 16 ticks per simulated day, 8am–4pm every 30 minutes
TICKS_PER_DAY = 16
_START_HOUR = 8

_UPCOMING_EVENTS: dict[str, list[str]] = {
    "regular": [
        "Architecture review", "Eng sync", "Sprint planning",
        "1:1 with manager", "Code review session", "Incident retro",
    ],
    "sparse": [
        "Paper reading club", "Research sync", "ML platform review",
        "Model eval review",
    ],
    "dense": [
        "Investor call", "Product review", "Customer demo",
        "Board prep", "Sales sync", "Fundraising debrief",
        "All-hands", "Hiring debrief",
    ],
}

_MEETING_DENSITY: dict[str, tuple[float, float]] = {
    "dense":   (0.65, 0.90),
    "regular": (0.25, 0.55),
    "sparse":  (0.00, 0.20),
}


def _tick_hour(tick: int) -> int:
    return _START_HOUR + tick // 2


def _daily_busy_ticks(persona: Persona, day: int) -> set[int]:
    """Return the set of ticks that are occupied by meetings on this simulated day."""
    rng = random.Random(hash((persona.name, day, "busy")) & 0xFFFFFFFF)
    lo, hi = _MEETING_DENSITY[persona.calendar_pattern]
    density = rng.uniform(lo, hi)
    n_busy = round(density * TICKS_PER_DAY)

    if persona.calendar_pattern == "regular":
        # Predictable slots: morning block + occasional afternoon
        candidates = list(range(2, 5)) + list(range(7, 10)) + list(range(11, 14))
        sample = rng.sample(candidates, min(n_busy, len(candidates)))
    elif persona.calendar_pattern == "dense":
        # Back-to-back, skew toward mid-day
        candidates = list(range(1, TICKS_PER_DAY))
        # Bias: weight middle ticks more heavily
        weights = [1 + abs(i - TICKS_PER_DAY // 2) * 0.1 for i in range(1, TICKS_PER_DAY)]
        sample = rng.choices(candidates, weights=weights, k=n_busy)
        sample = list(set(sample))
    else:  # sparse
        candidates = list(range(TICKS_PER_DAY))
        sample = rng.sample(candidates, min(n_busy, len(candidates)))

    return set(sample)


def _calendar_gap(tick: int, busy_ticks: set[int]) -> int:
    """Minutes until the next busy tick, capped at 120."""
    for future in range(tick + 1, TICKS_PER_DAY):
        if future in busy_ticks:
            return (future - tick) * 30
    return 120


def _minutes_since_last_meeting(tick: int, busy_ticks: set[int]) -> int:
    for past in range(tick - 1, -1, -1):
        if past in busy_ticks:
            return (tick - past) * 30
    return 999


def _location(persona: Persona, tick: int, day: int) -> Literal["desk", "commute", "gym", "cafe", "near_anchor", "unknown"]:
    rng = random.Random(hash((persona.name, day, tick, "loc")) & 0xFFFFFFFF)
    hour = _tick_hour(tick)
    if hour <= 8:
        return "commute" if rng.random() < 0.3 else "desk"
    if persona.calendar_pattern == "sparse" and rng.random() < 0.15:
        return "cafe"
    return persona.default_location  # type: ignore[return-value]


def sample_context(
    persona: Persona,
    day: int,
    tick: int,
    surfaces_today: int = 0,
    time_since_last_surface_minutes: int = 9999,
    busy_ticks: set[int] | None = None,
) -> ContextSnapshot:
    """Return a plausible ContextSnapshot for this persona at this moment."""
    if busy_ticks is None:
        busy_ticks = _daily_busy_ticks(persona, day)

    rng = random.Random(hash((persona.name, day, tick, "ctx")) & 0xFFFFFFFF)
    hour = _tick_hour(tick)
    gap = _calendar_gap(tick, busy_ticks)
    mins_since = _minutes_since_last_meeting(tick, busy_ticks)
    density_lo, density_hi = _MEETING_DENSITY[persona.calendar_pattern]
    meeting_density = round(rng.uniform(density_lo, density_hi), 2)
    location = _location(persona, tick, day)

    # Post-meeting window: useful signal for digest relevance
    post_meeting: int | None = None
    if 0 < mins_since <= 20:
        post_meeting = mins_since

    # Upcoming event (contextual relevance for matching)
    upcoming: str | None = None
    if gap <= 60:
        events = _UPCOMING_EVENTS[persona.calendar_pattern]
        upcoming = rng.choice(events)

    # Recent event (post-processing window)
    recent: str | None = None
    if 0 < mins_since <= 30:
        events = _UPCOMING_EVENTS[persona.calendar_pattern]
        recent = rng.choice(events)

    topical_affinity = infer_topical_affinity(
        location_type=location,  # type: ignore[arg-type]
        upcoming_event_title=upcoming,
        post_meeting_minutes=post_meeting,
        email_themes=[],
        communication_burst=False,
    )
    attention_capacity = infer_attention_capacity(
        calendar_gap_minutes=gap,
        meeting_density_today=meeting_density,
        surfaces_today=surfaces_today,
    )

    return ContextSnapshot(
        upcoming_event_title=upcoming,
        recent_event_title=recent,
        post_meeting_minutes=post_meeting,
        location_type=location,
        calendar_gap_minutes=gap,
        meeting_density_today=meeting_density,
        minutes_since_last_meeting=mins_since,
        surfaces_today=surfaces_today,
        time_since_last_surface_minutes=time_since_last_surface_minutes,
        topical_affinity=topical_affinity,
        attention_capacity=attention_capacity,
    )
