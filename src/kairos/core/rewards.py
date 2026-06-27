"""Map user feedback actions to bandit rewards."""

from __future__ import annotations

from kairos.models.schemas import FeedbackAction

# PLAN.md reward table (simplified for online bandit updates)
_REWARDS: dict[FeedbackAction, float | None] = {
    "acted": 1.0,
    "link_click": 0.8,
    "expanded": 0.4,
    "snoozed": None,  # re-queue only — no cluster penalty
    "dismissed": -0.4,
    "ignored": -0.6,
}


def reward_for_action(action: FeedbackAction) -> float | None:
    """Return derived reward, or None when bandit should not update."""
    return _REWARDS.get(action)


def bandit_deltas(reward: float) -> tuple[float, float]:
    """Split reward into α/β increments for Beta bandit."""
    if reward > 0:
        return reward, 0.0
    if reward < 0:
        return 0.0, abs(reward)
    return 0.0, 0.0
