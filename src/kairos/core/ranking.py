"""Ranking pipeline + interrupt gate (policy core)."""

from __future__ import annotations

from kairos.models.schemas import ContextSnapshot, SurfaceDecision
from kairos.observability.bus import event_bus


def evaluate_surface(
    context: ContextSnapshot,
    context_override: str | None = None,
) -> SurfaceDecision:
    """Run feasibility → vector search → bandit → interrupt gate. Stub until wired."""
    if context_override:
        event_bus.emit("context_override", context_override)

    # TODO: wire MongoDB $vectorSearch + Thompson sampling bandit
    decision = SurfaceDecision(
        should_surface=False,
        gate_reasons={
            "daily_budget": True,
            "calendar_gap": context.calendar_gap_minutes > 30,
            "min_gap": True,
            "score_threshold": False,
        },
        context=context,
    )
    event_bus.emit(
        "activity",
        "Ranking pipeline complete",
        should_surface=decision.should_surface,
        gate_reasons=decision.gate_reasons,
    )
    return decision
