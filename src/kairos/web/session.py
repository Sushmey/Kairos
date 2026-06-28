"""Resolve active Kairos user for web/API requests."""

from __future__ import annotations

from fastapi import Request

from kairos.config import settings

SESSION_COOKIE = "kairos_user_id"


def get_user_id(request: Request | None = None) -> str | None:
    """Cookie override, then KAIROS_USER_ID from environment."""
    if request is not None:
        cookie = request.cookies.get(SESSION_COOKIE)
        if cookie:
            return cookie
    return settings.kairos_user_id
