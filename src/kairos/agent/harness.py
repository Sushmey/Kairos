"""Kairos agent harness — Antigravity SDK orchestration layer."""

from __future__ import annotations

import logging

from google.antigravity import Agent

from kairos.agent.config import build_agent_config
from kairos.agent.prompts import DECISION_TURN_PROMPT
from kairos.core.heartbeat import heartbeat_service
from kairos.models.schemas import DeliveryMode, HeartbeatResult
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)


async def run_decision_cycle(delivery: DeliveryMode = "auto") -> HeartbeatResult:
    """Execute one heartbeat via policy core (direct path, no Antigravity loop)."""
    event_bus.emit("session", "Starting heartbeat")
    result = await heartbeat_service.run(delivery=delivery)
    event_bus.emit("session", "Heartbeat complete", status=result.status)
    return result


async def run_decision_cycle_via_agent() -> HeartbeatResult | None:
    """Execute one heartbeat via the Antigravity agent harness."""
    config = build_agent_config()
    event_bus.emit("session", "Starting agent heartbeat")

    async with Agent(config) as agent:
        response = await agent.chat(DECISION_TURN_PROMPT)
        text = await response.text()
        logger.info("Agent heartbeat complete: %s", (text or "")[:200])
        event_bus.emit("session", "Agent heartbeat complete", preview=(text or "")[:300])

        try:
            structured = await response.structured_output()
            if structured is not None:
                return HeartbeatResult.model_validate(structured)
        except (TypeError, ValueError):
            pass

    return None


async def run_interactive(prompt: str) -> str:
    """Run a single interactive turn (for MCP / Claude Code parity)."""
    config = build_agent_config()
    async with Agent(config) as agent:
        response = await agent.chat(prompt)
        return await response.text() or ""
