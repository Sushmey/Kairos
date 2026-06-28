"""Fuse heterogeneous sensors into a policy-facing ContextSnapshot."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from kairos.config import settings
from kairos.models.schemas import (
    AttentionCapacity,
    ContextSnapshot,
    TopicalAffinity,
)
from kairos.models.sensors import (
    CalendarEvent,
    EmailThread,
    calendar_events_to_dicts,
    email_threads_to_dicts,
)

LocationType = Literal["desk", "commute", "gym", "cafe", "near_anchor", "unknown"]


def _parse_event_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _event_start(event: dict[str, Any]) -> datetime | None:
    start = event.get("start") or {}
    if isinstance(start, dict):
        return _parse_event_time(start.get("dateTime") or start.get("date"))
    return _parse_event_time(event.get("startTime") or event.get("start"))


def _event_end(event: dict[str, Any]) -> datetime | None:
    end = event.get("end") or {}
    if isinstance(end, dict):
        return _parse_event_time(end.get("dateTime") or end.get("date"))
    return _parse_event_time(event.get("endTime") or event.get("end"))


def _event_title(event: dict[str, Any]) -> str:
    for key in ("summary", "title", "subject", "name"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def parse_calendar_events(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive calendar features from Google Calendar MCP-style event dicts."""
    now = now or datetime.now(timezone.utc)
    parsed: list[tuple[datetime, datetime, str]] = []
    for event in events:
        start = _event_start(event)
        if not start:
            continue
        end = _event_end(event) or start
        title = _event_title(event)
        parsed.append((start, end, title))

    parsed.sort(key=lambda row: row[0])
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)

    today = [(s, e, t) for s, e, t in parsed if s.date() == now.date()]
    meeting_minutes = sum(
        max(0, int((min(e, day_end) - max(s, day_start)).total_seconds() // 60))
        for s, e, t in today
        if e > s
    )
    waking_minutes = max(1, int((day_end - day_start).total_seconds() // 60) - 480)
    meeting_density = min(1.0, meeting_minutes / waking_minutes)

    upcoming_title: str | None = None
    upcoming_gap = 9999
    for start, _end, title in parsed:
        if start > now:
            gap = int((start - now).total_seconds() // 60)
            if gap < upcoming_gap:
                upcoming_gap = gap
                upcoming_title = title or None

    recent_title: str | None = None
    minutes_since_last = 9999
    post_meeting: int | None = None
    for start, end, title in parsed:
        if end <= now:
            mins = int((now - end).total_seconds() // 60)
            if mins < minutes_since_last:
                minutes_since_last = mins
                recent_title = title or None
            if 0 < mins <= 30 and (post_meeting is None or mins < post_meeting):
                post_meeting = mins

    calendar_gap = upcoming_gap if upcoming_gap < 9999 else 120

    return {
        "upcoming_event_title": upcoming_title,
        "recent_event_title": recent_title,
        "post_meeting_minutes": post_meeting,
        "calendar_gap_minutes": calendar_gap,
        "meeting_density_today": round(meeting_density, 2),
        "minutes_since_last_meeting": minutes_since_last if minutes_since_last < 9999 else 0,
    }


def _extract_email_themes(threads: list[dict[str, Any]]) -> list[str]:
    themes: list[str] = []
    seen: set[str] = set()
    for thread in threads:
        for key in ("subject", "snippet", "summary", "title"):
            raw = thread.get(key)
            if not isinstance(raw, str):
                continue
            text = raw.strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            themes.append(text[:120])
            break
        if len(themes) >= 8:
            break
    return themes


def infer_location_type(
    *,
    explicit: LocationType | None = None,
    lat: float | None = None,
    lng: float | None = None,
    hour: int | None = None,
) -> LocationType:
    if explicit and explicit != "unknown":
        return explicit
    if settings.kairos_location_type and settings.kairos_location_type != "unknown":
        return settings.kairos_location_type  # type: ignore[return-value]

    if lat is not None and lng is not None:
        for anchor in settings.location_anchors():
            alat, alng, label = anchor["lat"], anchor["lng"], anchor["label"]
            if _haversine_km(lat, lng, alat, alng) <= anchor.get("radius_km", 0.25):
                return label  # type: ignore[return-value]

    if hour is not None and hour <= 9:
        return "commute"
    return "unknown"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def infer_topical_affinity(
    *,
    location_type: LocationType,
    upcoming_event_title: str | None,
    post_meeting_minutes: int | None,
    email_themes: list[str],
    communication_burst: bool,
) -> TopicalAffinity:
    if communication_burst or (post_meeting_minutes and email_themes):
        return "triage"
    if location_type == "cafe":
        return "explore"
    if upcoming_event_title:
        return "work"
    if post_meeting_minutes and post_meeting_minutes <= 20:
        return "recovery"
    if location_type == "gym":
        return "recovery"
    return "work"


def infer_attention_capacity(
    *,
    calendar_gap_minutes: int,
    meeting_density_today: float,
    surfaces_today: int,
) -> AttentionCapacity:
    budget = settings.daily_surface_budget
    min_gap = settings.min_calendar_gap_minutes

    if calendar_gap_minutes < min_gap or surfaces_today >= budget:
        return "none"
    if calendar_gap_minutes >= 60 and meeting_density_today < 0.45:
        return "high"
    if calendar_gap_minutes >= 30:
        return "medium"
    return "low"


def fuse_headspace(
    *,
    calendar_events: list[CalendarEvent] | list[dict[str, Any]] | None = None,
    email_threads: list[EmailThread] | list[dict[str, Any]] | None = None,
    email_themes: list[str] | None = None,
    location_type: LocationType | None = None,
    lat: float | None = None,
    lng: float | None = None,
    surfaces_today: int | None = None,
    time_since_last_surface_minutes: int | None = None,
    now: datetime | None = None,
    sensor_sources: list[str] | None = None,
    **overrides: Any,
) -> ContextSnapshot:
    """Merge sensor readings into one ContextSnapshot."""
    cal_events = calendar_events_to_dicts(calendar_events) if calendar_events else []
    mail_threads = email_threads_to_dicts(email_threads) if email_threads else []
    now = now or datetime.now(timezone.utc)
    sources = list(sensor_sources or [])

    derived: dict[str, Any] = {
        "hour": now.hour,
        "day_of_week": now.weekday(),
        "is_weekend": now.weekday() >= 5,
        "surfaces_today": surfaces_today if surfaces_today is not None else 0,
        "time_since_last_surface_minutes": (
            time_since_last_surface_minutes
            if time_since_last_surface_minutes is not None
            else 9999
        ),
    }

    if cal_events:
        sources.append("calendar")
        derived.update(parse_calendar_events(cal_events, now=now))

    themes = list(email_themes or [])
    if mail_threads:
        sources.append("gmail")
        themes.extend(_extract_email_themes(mail_threads))
    # dedupe preserve order
    deduped: list[str] = []
    seen: set[str] = set()
    for theme in themes:
        key = theme.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(theme)
    themes = deduped[:8]

    if themes:
        sources.append("email")
    derived["email_themes"] = themes

    loc = infer_location_type(
        explicit=location_type,
        lat=lat,
        lng=lng,
        hour=now.hour,
    )
    if lat is not None and lng is not None:
        sources.append("geolocation")
    derived["location_type"] = loc
    derived["lat"] = lat
    derived["lng"] = lng

    post_meeting = derived.get("post_meeting_minutes")
    communication_burst = bool(
        post_meeting is not None and 0 < int(post_meeting) <= 20 and themes
    )
    derived["communication_burst"] = communication_burst

    derived["topical_affinity"] = infer_topical_affinity(
        location_type=loc,
        upcoming_event_title=derived.get("upcoming_event_title"),
        post_meeting_minutes=post_meeting,
        email_themes=themes,
        communication_burst=communication_burst,
    )
    derived["attention_capacity"] = infer_attention_capacity(
        calendar_gap_minutes=int(derived.get("calendar_gap_minutes", 0)),
        meeting_density_today=float(derived.get("meeting_density_today", 0.0)),
        surfaces_today=int(derived.get("surfaces_today", 0)),
    )
    derived["sensor_sources"] = sources
    derived["fused_at"] = now

    # Explicit overrides win (agent refinements)
    for key, value in overrides.items():
        if value is not None and key in ContextSnapshot.model_fields:
            derived[key] = value

    return ContextSnapshot.model_validate(derived)


def enrich_modes(snapshot: ContextSnapshot) -> ContextSnapshot:
    """Recompute derived modes after a manual patch (skip if LLM already composed)."""
    if "llm_compose" in snapshot.sensor_sources:
        burst = bool(
            snapshot.post_meeting_minutes is not None
            and 0 < snapshot.post_meeting_minutes <= 20
            and snapshot.email_themes
        )
        if burst == snapshot.communication_burst:
            return snapshot
        return snapshot.model_copy(update={"communication_burst": burst})

    loc = snapshot.location_type
    affinity = infer_topical_affinity(
        location_type=loc,
        upcoming_event_title=snapshot.upcoming_event_title,
        post_meeting_minutes=snapshot.post_meeting_minutes,
        email_themes=snapshot.email_themes,
        communication_burst=snapshot.communication_burst,
    )
    capacity = infer_attention_capacity(
        calendar_gap_minutes=snapshot.calendar_gap_minutes,
        meeting_density_today=snapshot.meeting_density_today,
        surfaces_today=snapshot.surfaces_today,
    )
    burst = bool(
        snapshot.post_meeting_minutes is not None
        and 0 < snapshot.post_meeting_minutes <= 20
        and snapshot.email_themes
    )
    return snapshot.model_copy(
        update={
            "topical_affinity": affinity,
            "attention_capacity": capacity,
            "communication_burst": burst,
        }
    )
