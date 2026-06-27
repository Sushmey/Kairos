"""Kairos agent harness — Antigravity SDK orchestration layer."""

from __future__ import annotations

import logging

from google.antigravity import Agent

from kairos.agent.config import build_agent_config
from kairos.agent.prompts import DECISION_TURN_PROMPT
from kairos.models.schemas import SurfaceDecision
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)


async def run_decision_cycle() -> SurfaceDecision | None:
    """Execute one bandit decision cycle via the Antigravity agent harness."""
    config = build_agent_config()
    event_bus.emit("session", "Starting decision cycle")

    async with Agent(config) as agent:
        response = await agent.chat(DECISION_TURN_PROMPT)
        text = await response.text()
        logger.info("Decision cycle complete: %s", (text or "")[:200])
        event_bus.emit("session", "Decision cycle complete", preview=(text or "")[:300])

        try:
            structured = await response.structured_output()
            if structured is not None:
                return SurfaceDecision.model_validate(structured)
        except (TypeError, ValueError):
            pass

    return None


async def run_interactive(prompt: str) -> str:
    """Run a single interactive turn (for MCP / Claude Code parity)."""
    config = build_agent_config()
    async with Agent(config) as agent:
        response = await agent.chat(prompt)
        return await response.text() or ""
