"""Google Calendar API — events for headspace fusion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from kairos.google.credentials import credentials_from_settings


def fetch_calendar_events(
    *,
    hours_back: int = 12,
    hours_forward: int = 36,
    calendar_id: str = "primary",
    credentials: Credentials | None = None,
) -> list[dict[str, Any]]:
    """Return events in MCP-compatible shape for fuse_headspace."""
    creds = credentials or credentials_from_settings()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(hours=hours_back)).isoformat()
    time_max = (now + timedelta(hours=hours_forward)).isoformat()

    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=50,
        )
        .execute()
    )
    items = result.get("items") or []
    return [_normalize_event(ev) for ev in items]


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start") or {}
    end = event.get("end") or {}
    return {
        "id": event.get("id"),
        "summary": event.get("summary") or "(no title)",
        "start": {
            "dateTime": start.get("dateTime"),
            "date": start.get("date"),
        },
        "end": {
            "dateTime": end.get("dateTime"),
            "date": end.get("date"),
        },
        "status": event.get("status"),
    }
