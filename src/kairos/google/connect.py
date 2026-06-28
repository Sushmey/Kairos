"""Channel-agnostic Google OAuth — loopback callback for MCP, CLI, and agents."""

from __future__ import annotations

import asyncio
import secrets
import threading
import webbrowser
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from kairos.config import settings
from kairos.db.google_tokens import save_google_connection
from kairos.db.oauth_states import consume_oauth_state, save_oauth_state
from kairos.google.credentials import GoogleAuthError
from kairos.google.scopes import HEADSPACE_SCOPES
from kairos.ingest.x.callback_server import OAuthCallbackListener


@dataclass
class GoogleOAuthCallbackResult:
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    scopes: list[str]
    token_expiry: object | None


@dataclass
class _ConnectSession:
    state: str
    done: threading.Event = field(default_factory=threading.Event)
    result: GoogleOAuthCallbackResult | None = None
    error: str | None = None
    listener: OAuthCallbackListener | None = None


_sessions: dict[str, _ConnectSession] = {}
_sessions_lock = threading.Lock()


def _redirect_parts() -> tuple[str, int, str]:
    redirect = settings.google_oauth_redirect_uri
    parsed = urlparse(redirect)
    if parsed.scheme not in ("http", "https"):
        raise GoogleAuthError(f"Redirect URI must be http(s): {redirect!r}")
    host = parsed.hostname or "127.0.0.1"
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    return host, port, path


def _client_config() -> dict:
    if not settings.google_client_id or not settings.google_client_secret:
        raise GoogleAuthError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required. "
            "See docs/GOOGLE_WORKSPACE_SETUP.md"
        )
    redirect = settings.google_oauth_redirect_uri
    return {
        "installed": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect, "http://localhost"],
        }
    }


def _flow(*, state: str) -> Flow:
    return Flow.from_client_config(
        _client_config(),
        scopes=HEADSPACE_SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
        state=state,
    )


async def _exchange_code(code: str, state: str) -> GoogleOAuthCallbackResult:
    if not await consume_oauth_state(state):
        raise GoogleAuthError("Invalid or expired OAuth state")

    flow = _flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    if not creds or not creds.token:
        raise GoogleAuthError("Google did not return credentials")
    if not creds.refresh_token:
        raise GoogleAuthError(
            "No refresh token — revoke app access at myaccount.google.com/permissions "
            "and connect again with prompt=consent."
        )

    profile = (
        build("oauth2", "v2", credentials=creds, cache_discovery=False)
        .userinfo()
        .get()
        .execute()
    )
    user_id = profile.get("id")
    email = profile.get("email") or ""
    if not user_id:
        raise GoogleAuthError("Google userinfo did not return an id")

    return GoogleOAuthCallbackResult(
        user_id=user_id,
        email=email,
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        scopes=list(creds.scopes or HEADSPACE_SCOPES),
        token_expiry=creds.expiry,
    )


async def _persist_connection(result: GoogleOAuthCallbackResult) -> None:
    await save_google_connection(
        user_id=result.user_id,
        email=result.email,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        scopes=result.scopes,
        token_expiry=result.token_expiry,
    )


def _finish_session(session: _ConnectSession, result: GoogleOAuthCallbackResult) -> None:
    session.result = result
    session.done.set()


def _fail_session(session: _ConnectSession, message: str) -> None:
    session.error = message
    session.done.set()


def _on_callback(session: _ConnectSession, code: str | None, state: str | None, error: str | None) -> None:
    if error:
        _fail_session(session, f"Google OAuth error: {error}")
        return
    if not code or state != session.state:
        _fail_session(session, "OAuth callback missing code or state mismatch")
        return
    try:
        result = asyncio.run(_exchange_code(code, state))
        asyncio.run(_persist_connection(result))
        _finish_session(session, result)
    except Exception as exc:  # noqa: BLE001 — surface to waiter
        _fail_session(session, str(exc))


def _watch_listener(session: _ConnectSession) -> None:
    assert session.listener is not None
    try:
        callback = session.listener.wait(timeout=settings.google_oauth_timeout_seconds)
    except TimeoutError:
        _fail_session(session, "Timed out waiting for Google OAuth callback")
        return
    _on_callback(session, callback.code, callback.state, callback.error)


async def start_google_connect(*, open_browser: bool = False) -> dict[str, Any]:
    """Start loopback OAuth — returns URL for user consent."""
    state = secrets.token_urlsafe(32)
    await save_oauth_state(state)

    host, port, path = _redirect_parts()
    listener = OAuthCallbackListener(host=host, port=port, path=path)
    listener.start()

    session = _ConnectSession(state=state, listener=listener)
    with _sessions_lock:
        _sessions[state] = session

    flow = _flow(state=state)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    watcher = threading.Thread(target=_watch_listener, args=(session,), daemon=True)
    watcher.start()

    if open_browser:
        webbrowser.open(auth_url)

    return {
        "status": "pending",
        "state": state,
        "authorization_url": auth_url,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "instructions": (
            "Open authorization_url in a browser, sign in with Google, and approve access. "
            "Then call wait_google_connect(state=...) or connect_google(blocking=True)."
        ),
    }


def wait_google_connect(
    state: str,
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Wait for the user to complete Google consent on the loopback callback."""
    timeout = timeout_seconds if timeout_seconds is not None else settings.google_oauth_timeout_seconds
    with _sessions_lock:
        session = _sessions.get(state)
    if not session:
        return {"status": "error", "message": f"Unknown OAuth state: {state}"}

    if not session.done.wait(timeout=timeout):
        return {
            "status": "timeout",
            "state": state,
            "message": f"No callback within {timeout:.0f}s — retry start_google_connect()",
        }

    with _sessions_lock:
        _sessions.pop(state, None)

    if session.error:
        return {"status": "error", "state": state, "message": session.error}

    result = session.result
    if not result:
        return {"status": "error", "state": state, "message": "OAuth completed without result"}

    return {
        "status": "connected",
        "user_id": result.user_id,
        "email": result.email,
        "scopes": result.scopes,
        "message": "Google connected — use sync_google_headspace(user_id=...)",
    }


def google_connect_status(state: str | None = None) -> dict[str, Any]:
    """Non-blocking status for an in-flight OAuth session."""
    if not state:
        with _sessions_lock:
            pending = list(_sessions.keys())
        return {"pending_states": pending}

    with _sessions_lock:
        session = _sessions.get(state)
    if not session:
        return {"status": "unknown", "state": state}
    if session.done.is_set():
        if session.error:
            return {"status": "error", "state": state, "message": session.error}
        if session.result:
            return {
                "status": "connected",
                "state": state,
                "user_id": session.result.user_id,
                "email": session.result.email,
            }
    return {"status": "pending", "state": state}


async def connect_google(
    *,
    open_browser: bool = False,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Start OAuth, optionally open browser, block until callback completes."""
    start = await start_google_connect(open_browser=open_browser)
    if start.get("status") != "pending":
        return start
    waited = wait_google_connect(start["state"], timeout_seconds=timeout_seconds)
    if waited.get("status") == "connected":
        waited["authorization_url"] = start["authorization_url"]
    return waited
