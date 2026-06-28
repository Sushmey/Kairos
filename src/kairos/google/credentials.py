"""Load Google OAuth credentials per user or from dev .env."""

from __future__ import annotations

from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from kairos.config import settings
from kairos.db.google_tokens import load_google_connection, update_google_tokens
from kairos.google.scopes import HEADSPACE_SCOPES


class GoogleAuthError(RuntimeError):
    """Google OAuth or API configuration error."""


def _credentials_from_record(
    record: dict,
    *,
    scopes: list[str] | None = None,
) -> Credentials:
    scopes = scopes or list(record.get("scopes") or HEADSPACE_SCOPES)
    expiry = record.get("token_expiry")
    if expiry and getattr(expiry, "tzinfo", None) is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    return Credentials(
        token=record.get("access_token"),
        refresh_token=record.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=scopes,
        expiry=expiry,
    )


async def credentials_for_user(
    user_id: str,
    *,
    scopes: list[str] | None = None,
) -> Credentials:
    """Build refreshable credentials for a connected user."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise GoogleAuthError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required. "
            "See docs/GOOGLE_WORKSPACE_SETUP.md"
        )

    record = await load_google_connection(user_id)
    if not record:
        raise GoogleAuthError(
            f"User {user_id} has not connected Google. "
            "Run connect_google via MCP or: kairos google connect"
        )

    creds = _credentials_from_record(record, scopes=scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        await update_google_tokens(
            user_id,
            access_token=creds.token or "",
            token_expiry=creds.expiry,
        )
    if not creds.valid:
        raise GoogleAuthError("Google credentials invalid — reconnect Google in the web app.")
    return creds


def credentials_from_settings(*, scopes: list[str] | None = None) -> Credentials:
    """Dev fallback: single-user tokens from .env (CLI only)."""
    scopes = scopes or HEADSPACE_SCOPES
    if not settings.google_client_id or not settings.google_client_secret:
        raise GoogleAuthError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required. "
            "See docs/GOOGLE_WORKSPACE_SETUP.md"
        )
    if not settings.google_refresh_token:
        raise GoogleAuthError(
            "GOOGLE_REFRESH_TOKEN missing. Run: kairos google connect (or connect_google MCP tool)"
        )

    record = {
        "access_token": settings.google_access_token,
        "refresh_token": settings.google_refresh_token,
        "scopes": scopes,
    }
    creds = _credentials_from_record(record, scopes=scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        raise GoogleAuthError("Google credentials invalid. Reconnect or run: kairos google auth")
    return creds


async def user_has_google(user_id: str) -> bool:
    record = await load_google_connection(user_id)
    return record is not None


def auth_configured_for_env() -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_refresh_token
    )
