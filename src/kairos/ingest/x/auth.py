"""CLI-oriented X OAuth helpers."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from kairos.config import settings
from kairos.ingest.x.callback_server import OAuthCallbackListener
from kairos.ingest.x.client import XApiClient, XApiError
from kairos.ingest.x.oauth import (
    DEFAULT_SCOPES,
    OAuthTokens,
    build_authorize_url,
    exchange_authorization_code,
    generate_pkce_pair,
    generate_state,
    refresh_access_token,
)
from kairos.util.env_file import update_env_file


@dataclass
class RefreshEnvResult:
    tokens: OAuthTokens
    env_path: Path
    keys_written: list[str]


@dataclass
class AuthEnvResult:
    tokens: OAuthTokens
    user_id: str
    username: str | None
    env_path: Path
    keys_written: list[str]


@dataclass
class WhoamiEnvResult:
    user_id: str
    username: str | None
    name: str | None
    env_path: Path
    keys_written: list[str]


def _parse_redirect_uri(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    if parsed.scheme not in ("http", "https"):
        raise XApiError(f"Redirect URI must be http(s): {redirect_uri!r}")
    host = parsed.hostname or "127.0.0.1"
    # Bind listener on loopback; localhost and 127.0.0.1 both reach the same socket.
    if host in ("localhost", "::1"):
        host = "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    return host, port, path


def _oauth_env_updates(tokens: OAuthTokens, user_id: str | None = None) -> dict[str, str]:
    updates: dict[str, str] = {"X_ACCESS_TOKEN": tokens.access_token}
    if tokens.refresh_token:
        updates["X_REFRESH_TOKEN"] = tokens.refresh_token
    if user_id:
        updates["X_USER_ID"] = user_id
    return updates


async def refresh_tokens_to_env(
    env_path: Path,
    *,
    dry_run: bool = False,
) -> RefreshEnvResult:
    """Refresh access token and persist to .env."""
    tokens = await refresh_access_token()
    updates = _oauth_env_updates(tokens)

    keys_written: list[str] = []
    if not dry_run:
        keys_written = update_env_file(env_path, updates)

    return RefreshEnvResult(tokens=tokens, env_path=env_path, keys_written=keys_written)


async def run_pkce_auth_flow(
    env_path: Path,
    *,
    redirect_uri: str | None = None,
    scopes: str | None = None,
    open_browser: bool = True,
    timeout: float = 300.0,
) -> AuthEnvResult:
    """Run OAuth 2.0 Authorization Code + PKCE and persist tokens + user id to .env."""
    client_id = settings.x_client_id
    if not client_id:
        raise XApiError(
            "X_CLIENT_ID is not configured. Add it to .env from the X Developer Portal."
        )

    redirect = redirect_uri or settings.x_oauth_redirect_uri
    scope = scopes or settings.x_oauth_scopes or DEFAULT_SCOPES
    code_verifier, code_challenge = generate_pkce_pair()
    state = generate_state()

    authorize_url = build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect,
        scope=scope,
        state=state,
        code_challenge=code_challenge,
    )

    host, port, path = _parse_redirect_uri(redirect)
    listener = OAuthCallbackListener(host=host, port=port, path=path)
    listener.start()

    print("X OAuth — before continuing, verify Developer Portal settings:")
    print(f"  Callback URI must be EXACTLY: {redirect}")
    print("  Log into https://x.com in this browser first, then authorize.")
    print("  Run `kairos x auth-check` for a full checklist.\n")
    print(f"Listening for callback on http://{host}:{port}{path}")
    print("\nOpen this URL to authorize Kairos:\n")
    print(authorize_url)
    print()

    if open_browser:
        webbrowser.open(authorize_url)

    callback = listener.wait(timeout=timeout)

    if callback.error:
        detail = callback.error_description or callback.error
        raise XApiError(f"OAuth authorization denied: {detail}")

    if callback.state != state:
        raise XApiError("OAuth state mismatch — possible CSRF; try again.")

    if not callback.code:
        raise XApiError("OAuth callback missing authorization code")

    tokens = await exchange_authorization_code(
        code=callback.code,
        code_verifier=code_verifier,
        redirect_uri=redirect,
    )

    client = XApiClient(access_token=tokens.access_token)
    me = await client.get_me()
    user = me["data"]
    user_id = user["id"]
    username = user.get("username")

    updates = _oauth_env_updates(tokens, user_id=user_id)
    keys_written = update_env_file(env_path, updates)

    return AuthEnvResult(
        tokens=tokens,
        user_id=user_id,
        username=username,
        env_path=env_path,
        keys_written=keys_written,
    )


async def fetch_x_user_profile(*, access_token: str | None = None) -> dict[str, str | None]:
    """Return id, username, name for the authenticated user."""
    client = XApiClient(access_token=access_token)
    me = await client.get_me()
    user = me["data"]
    return {
        "user_id": user["id"],
        "username": user.get("username"),
        "name": user.get("name"),
    }


async def persist_x_user_id(env_path: Path) -> WhoamiEnvResult:
    """Resolve numeric user id via /2/users/me and write X_USER_ID to .env."""
    profile = await fetch_x_user_profile()
    user_id = profile["user_id"]
    if not user_id:
        raise XApiError("GET /2/users/me did not return a user id")

    keys_written = update_env_file(env_path, {"X_USER_ID": user_id})
    return WhoamiEnvResult(
        user_id=user_id,
        username=profile.get("username"),
        name=profile.get("name"),
        env_path=env_path,
        keys_written=keys_written,
    )
