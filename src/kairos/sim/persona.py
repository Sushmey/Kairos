"""Synthetic user personas for gym simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Persona:
    name: str
    calendar_pattern: Literal["dense", "sparse", "regular"]
    engagement_style: Literal["engaged", "dismissive", "snoozer"]
    # Maps topic keyword substrings → affinity weight 0–1.
    # Matched against cluster names via substring; highest match wins.
    topic_weights: dict[str, float]
    active_hours: tuple[int, int]  # (start_hour, end_hour) inclusive
    # Pairs of (start_hour, end_hour) for deep-work blocks where interruptions are rare
    deep_work_blocks: list[tuple[int, int]] = field(default_factory=list)
    avg_meetings_per_day: int = 3
    default_location: Literal["desk", "commute", "cafe", "unknown"] = "desk"


# ── Cast ────────────────────────────────────────────────────────────────────

ALEX = Persona(
    name="alex",
    calendar_pattern="regular",
    engagement_style="snoozer",
    topic_weights={
        "software": 0.9,
        "distributed": 0.88,
        "system": 0.82,
        "infra": 0.80,
        "engineering": 0.75,
        "database": 0.70,
        "architecture": 0.72,
        "ml": 0.40,
        "ai": 0.45,
        "security": 0.50,
        "startup": 0.30,
        "product": 0.25,
    },
    active_hours=(9, 18),
    deep_work_blocks=[(9, 11), (14, 16)],
    avg_meetings_per_day=3,
    default_location="desk",
)

MAYA = Persona(
    name="maya",
    calendar_pattern="sparse",
    engagement_style="engaged",
    topic_weights={
        "ml": 0.95,
        "machine learning": 0.95,
        "ai": 0.90,
        "research": 0.88,
        "paper": 0.85,
        "model": 0.82,
        "training": 0.80,
        "gpu": 0.75,
        "distributed": 0.60,
        "system": 0.50,
        "software": 0.45,
        "startup": 0.35,
    },
    active_hours=(8, 17),
    deep_work_blocks=[(8, 12)],
    avg_meetings_per_day=1,
    default_location="desk",
)

JORDAN = Persona(
    name="jordan",
    calendar_pattern="dense",
    engagement_style="dismissive",
    topic_weights={
        "startup": 0.90,
        "product": 0.88,
        "growth": 0.85,
        "business": 0.80,
        "fundraising": 0.78,
        "market": 0.75,
        "ai": 0.55,
        "software": 0.40,
        "engineering": 0.30,
        "system": 0.25,
        "ml": 0.35,
    },
    active_hours=(8, 20),
    deep_work_blocks=[],
    avg_meetings_per_day=7,
    default_location="desk",
)

ALL_PERSONAS: dict[str, Persona] = {
    "alex": ALEX,
    "maya": MAYA,
    "jordan": JORDAN,
}


def topic_fit(persona: Persona, cluster_name: str) -> float:
    """Return 0–1 affinity of a persona for a cluster name via substring match."""
    name_lower = cluster_name.lower()
    best = 0.15  # default baseline — anything might occasionally be surfaced
    for keyword, weight in persona.topic_weights.items():
        if keyword in name_lower:
            best = max(best, weight)
    return best
