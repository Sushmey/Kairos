"""Kairos ADK root agent — Google Workspace MCP + policy tools."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext

from kairos.agent.mcp_auth import (
    CALENDAR_MCP_URL,
    GMAIL_MCP_URL,
    google_mcp_headers,
)
from kairos.agent.prompts import KAIROS_INSTRUCTION
from kairos.agent.tools import (
    connect_google,
    fuse_headspace_context,
    get_cluster_summary,
    get_current_context,
    google_connect_status,
    record_feedback,
    run_heartbeat,
    set_context,
    start_google_connect,
    wait_google_connect,
)
from kairos.config import settings
from kairos.models.schemas import HeartbeatResult
from kairos.observability.bus import event_bus

APP_NAME = "kairos"
AGENT_NAME = "kairos_decision_agent"

_last_heartbeat: HeartbeatResult | None = None


def pop_last_heartbeat() -> HeartbeatResult | None:
    global _last_heartbeat
    result = _last_heartbeat
    _last_heartbeat = None
    return result


async def _after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> dict | None:
    event_bus.emit(
        "tool_call",
        f"Tool {tool.name} completed",
        tool=tool.name,
    )
    if tool.name == "run_heartbeat" and isinstance(tool_response, dict):
        global _last_heartbeat
        try:
            _last_heartbeat = HeartbeatResult.model_validate(tool_response)
        except (TypeError, ValueError):
            pass
    return None


async def _after_agent_callback(callback_context: CallbackContext) -> None:
    session = callback_context.session
    events = session.events if session else []
    for event in reversed(events):
        if event.author != AGENT_NAME or not event.content:
            continue
        parts = event.content.parts or []
        text = "".join(p.text or "" for p in parts if hasattr(p, "text"))
        if text:
            event_bus.emit("turn", "Agent turn complete", preview=text[:500])
            break


def _workspace_mcp_toolsets() -> list[McpToolset]:
    return [
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=CALENDAR_MCP_URL),
            header_provider=google_mcp_headers,
            tool_name_prefix="calendar_",
        ),
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=GMAIL_MCP_URL),
            header_provider=google_mcp_headers,
            tool_name_prefix="gmail_",
        ),
    ]


def build_root_agent() -> LlmAgent:
    """Build the Kairos ADK agent with Workspace MCP and policy tools."""
    return LlmAgent(
        name=AGENT_NAME,
        model=settings.gemini_model,
        instruction=KAIROS_INSTRUCTION,
        mode="chat",
        tools=[
            *_workspace_mcp_toolsets(),
            connect_google,
            start_google_connect,
            wait_google_connect,
            google_connect_status,
            fuse_headspace_context,
            get_current_context,
            set_context,
            get_cluster_summary,
            run_heartbeat,
            record_feedback,
        ],
        after_tool_callback=_after_tool_callback,
        after_agent_callback=_after_agent_callback,
    )


root_agent = build_root_agent()
