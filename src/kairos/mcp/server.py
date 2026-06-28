"""Kairos MCP server — FastMCP wrapper over policy tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kairos.agent.tools import ALL_TOOLS

INSTRUCTIONS = """\
Kairos learns WHEN to surface bookmark topic clusters — not search on demand.

Google Calendar/Gmail access uses loopback OAuth (not the web app):
1. connect_google() — blocks until user consents at authorization_url (:8766 callback)
   OR start_google_connect() → user opens URL → wait_google_connect(state=...)
2. Set KAIROS_USER_ID to returned user_id (or use --write-env via CLI)
3. sync_google_headspace(user_id=...)
4. run_heartbeat(delivery='return_only')
5. On dismiss/snooze/click: record_feedback(notification_id, action)

Silence (KAIROS_OK) is correct and common. Do not force a digest every tick.
"""

mcp = FastMCP(
    name="kairos",
    instructions=INSTRUCTIONS,
)

for _tool in ALL_TOOLS:
    mcp.add_tool(_tool)


def run_stdio() -> None:
    """Run MCP server on stdio (default for Claude Code / Cursor)."""
    mcp.run(transport="stdio")


def run_sse(*, host: str = "127.0.0.1", port: int = 8421) -> None:
    """Run MCP server with SSE transport (debug / HTTP clients)."""
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="sse")
