"""Typed sensor payloads for headspace fusion (Calendar, Gmail, web fuse API)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CalendarEventTime(BaseModel):
    """Google Calendar event start/end — timed or all-day."""

    dateTime: str | None = None
    date: str | None = None


class CalendarEvent(BaseModel):
    """Calendar event from Google API, Workspace MCP, or manual fuse."""

    id: str | None = None
    summary: str | None = None
    title: str | None = None
    subject: str | None = None
    name: str | None = None
    start: CalendarEventTime | dict[str, Any] | str | None = None
    end: CalendarEventTime | dict[str, Any] | str | None = None
    startTime: str | None = None
    endTime: str | None = None
    status: str | None = None

    model_config = {"extra": "allow"}

    def as_fuse_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class EmailThread(BaseModel):
    """Gmail thread summary for theme extraction."""

    id: str | None = None
    subject: str | None = None
    snippet: str | None = None
    threadId: str | None = None

    model_config = {"extra": "allow"}

    def as_fuse_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class FuseHeadspacePayload(BaseModel):
    """Body for POST /api/context/fuse and MCP fuse_headspace_context."""

    calendar_events: list[CalendarEvent] = Field(default_factory=list)
    email_threads: list[EmailThread] = Field(default_factory=list)
    email_themes: list[str] | None = None
    location_type: str | None = None
    lat: float | None = None
    lng: float | None = None
    surfaces_today: int | None = None
    time_since_last_surface_minutes: int | None = None


def parse_calendar_events(events: list[CalendarEvent] | list[dict[str, Any]] | None) -> list[CalendarEvent]:
    if not events:
        return []
    parsed: list[CalendarEvent] = []
    for item in events:
        if isinstance(item, CalendarEvent):
            parsed.append(item)
        else:
            parsed.append(CalendarEvent.model_validate(item))
    return parsed


def parse_email_threads(threads: list[EmailThread] | list[dict[str, Any]] | None) -> list[EmailThread]:
    if not threads:
        return []
    parsed: list[EmailThread] = []
    for item in threads:
        if isinstance(item, EmailThread):
            parsed.append(item)
        else:
            parsed.append(EmailThread.model_validate(item))
    return parsed


def calendar_events_to_dicts(events: list[CalendarEvent] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [e.as_fuse_dict() if isinstance(e, CalendarEvent) else e for e in parse_calendar_events(events)]


def email_threads_to_dicts(threads: list[EmailThread] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [t.as_fuse_dict() if isinstance(t, EmailThread) else t for t in parse_email_threads(threads)]
