"""Google Workspace MCP auth — bearer tokens from per-user OAuth."""

from __future__ import annotations

import time
from typing import Any

from google.adk.agents.readonly_context import ReadonlyContext

from kairos.config import settings
from kairos.google.credentials import GoogleAuthError, credentials_from_settings

CALENDAR_MCP_URL = "https://calendarmcp.googleapis.com/mcp/v1"
GMAIL_MCP_URL = "https://gmailmcp.googleapis.com/mcp/v1"

_MCP_ACCEPT = "application/json, text/event-stream"
_token_cache: dict[str, tuple[str, float]] = {}


async def warm_google_mcp_auth(user_id: str | None = None) -> str:
    """Load and cache a Google access token for Workspace MCP toolsets."""
    uid = user_id or settings.kairos_user_id
    if not uid:
        if settings.google_refresh_token:
            creds = credentials_from_settings()
            token = creds.token or ""
            _token_cache["__env__"] = (token, time.time() + 3300)
            return token
        raise GoogleAuthError(
            "KAIROS_USER_ID required for Google Workspace MCP. "
            "Run connect_google or kairos google connect."
        )

    from kairos.google.credentials import credentials_for_user

    creds = await credentials_for_user(uid)
    token = creds.token or ""
    expiry = creds.expiry.timestamp() if creds.expiry else time.time() + 3300
    _token_cache[uid] = (token, expiry - 60)
    return token


def _resolve_user_id(context: ReadonlyContext | None) -> str:
    if context and context.user_id:
        return context.user_id
    if settings.kairos_user_id:
        return settings.kairos_user_id
    if settings.google_refresh_token:
        return "__env__"
    return ""


def _cached_token(user_id: str) -> str | None:
    entry = _token_cache.get(user_id)
    if not entry:
        return None
    token, expires_at = entry
    if time.time() >= expires_at:
        return None
    return token


def google_mcp_headers(context: ReadonlyContext) -> dict[str, str]:
    """Header provider for Google Workspace McpToolsets."""
    user_id = _resolve_user_id(context)
    token = _cached_token(user_id) if user_id else None
    if not token:
        raise GoogleAuthError(
            "Google MCP token not warmed. Call connect_google first or run warm_google_mcp_auth."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": _MCP_ACCEPT,
    }


def invalidate_token_cache(user_id: str | None = None) -> None:
    if user_id:
        _token_cache.pop(user_id, None)
    else:
        _token_cache.clear()
