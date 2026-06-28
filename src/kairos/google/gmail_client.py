"""Gmail API — recent threads for headspace fusion."""

from __future__ import annotations

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from kairos.google.credentials import credentials_from_settings


def fetch_recent_email_threads(
    *,
    query: str = "newer_than:2d",
    max_results: int = 10,
    credentials: Credentials | None = None,
) -> list[dict[str, Any]]:
    """Return thread summaries compatible with fuse_headspace email_threads."""
    creds = credentials or credentials_from_settings()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    listed = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    messages = listed.get("messages") or []
    threads: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in messages:
        msg_id = item.get("id")
        if not msg_id:
            continue
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
        thread_id = detail.get("threadId") or msg_id
        if thread_id in seen:
            continue
        seen.add(thread_id)

        subject = _header(detail, "Subject") or "(no subject)"
        snippet = detail.get("snippet") or ""
        threads.append(
            {
                "id": thread_id,
                "subject": subject,
                "snippet": snippet,
            }
        )
    return threads


def _header(message: dict[str, Any], name: str) -> str | None:
    for header in message.get("payload", {}).get("headers") or []:
        if header.get("name") == name:
            return header.get("value")
    return None
