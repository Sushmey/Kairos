"""Observability hooks for the Antigravity agent harness."""

from __future__ import annotations

from google.antigravity import types
from google.antigravity.hooks import post_tool_call, post_turn

from kairos.observability.bus import event_bus


@post_tool_call
async def log_tool_call(result: types.ToolResult) -> None:
    event_bus.emit(
        "tool_call",
        f"Tool {result.name} completed",
        tool=result.name,
    )


@post_turn
async def log_turn(text: str) -> None:
    preview = (text or "")[:500]
    event_bus.emit("turn", "Agent turn complete", preview=preview)


OBSERVABILITY_HOOKS = [log_tool_call, log_turn]
