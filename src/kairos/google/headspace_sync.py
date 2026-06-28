"""Fetch Google sensors and fuse headspace for one user."""

from __future__ import annotations

from typing import Any, Literal

from kairos.core.context import write_context
from kairos.core.intelligence import fuse_headspace_intelligent
from kairos.core.moment import context_class, moment_text
from kairos.google.calendar_client import fetch_calendar_events
from kairos.google.credentials import GoogleAuthError, credentials_for_user, credentials_from_settings
from kairos.google.gmail_client import fetch_recent_email_threads
from kairos.models.schemas import ContextSnapshot

LocationType = Literal["desk", "commute", "gym", "cafe", "near_anchor", "unknown"]


async def fuse_and_persist_headspace(
    *,
    user_id: str | None,
    calendar_events: list[dict[str, Any]] | None = None,
    email_threads: list[dict[str, Any]] | None = None,
    email_themes: list[str] | None = None,
    location_type: LocationType | None = None,
    lat: float | None = None,
    lng: float | None = None,
    surfaces_today: int | None = None,
    time_since_last_surface_minutes: int | None = None,
    sensor_sources: list[str] | None = None,
    persist: bool = True,
) -> ContextSnapshot:
    """Single fuse entry — used by MCP tools, web API, and Google sync."""
    snapshot = fuse_headspace_intelligent(
        calendar_events=calendar_events,
        email_threads=email_threads,
        email_themes=email_themes,
        location_type=location_type,
        lat=lat,
        lng=lng,
        surfaces_today=surfaces_today,
        time_since_last_surface_minutes=time_since_last_surface_minutes,
        sensor_sources=sensor_sources,
    )
    if persist:
        await write_context(snapshot, user_id=user_id)
    return snapshot


async def sync_google_headspace(
    user_id: str | None,
    *,
    persist: bool = True,
    location_type: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    use_env_fallback: bool = False,
) -> dict[str, Any]:
    """Pull Calendar + Gmail for user_id, fuse, optionally persist."""
    try:
        if use_env_fallback:
            creds = credentials_from_settings()
        elif user_id:
            creds = await credentials_for_user(user_id)
        else:
            raise GoogleAuthError("user_id required unless use_env_fallback=True")
    except GoogleAuthError as exc:
        return {"ok": False, "issues": [str(exc)]}

    issues: list[str] = []
    calendar_events: list[dict[str, Any]] = []
    email_threads: list[dict[str, Any]] = []

    try:
        calendar_events = fetch_calendar_events(credentials=creds)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"Calendar API failed: {exc}")

    try:
        email_threads = fetch_recent_email_threads(credentials=creds)
    except Exception as exc:
        issues.append(f"Gmail API failed: {exc}")

    if not calendar_events and not email_threads and not issues:
        issues.append("No calendar events or email threads returned.")

    snapshot = await fuse_and_persist_headspace(
        user_id=user_id,
        calendar_events=calendar_events or None,
        email_threads=email_threads or None,
        location_type=location_type,
        lat=lat,
        lng=lng,
        sensor_sources=["google_calendar_api", "google_gmail_api"],
        persist=persist,
    )

    highlights = _highlights(snapshot, calendar_events, email_threads)
    ok = bool(highlights) and not all(
        "returned 0 events" in i for i in issues if "Calendar" in i
    )

    return {
        "ok": ok or bool(highlights),
        "user_id": user_id,
        "issues": issues,
        "highlights": highlights,
        "calendar_event_count": len(calendar_events),
        "email_thread_count": len(email_threads),
        "context": snapshot.model_dump(mode="json"),
        "moment_text": moment_text(snapshot),
        "context_class": context_class(snapshot),
    }


def _highlights(
    snap: ContextSnapshot,
    calendar_events: list[dict[str, Any]],
    email_threads: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = []
    if snap.calendar_gap_minutes >= 30:
        lines.append(f"Calendar gap: {snap.calendar_gap_minutes} min")
    if snap.upcoming_event_title:
        lines.append(f"Upcoming: {snap.upcoming_event_title}")
    if snap.recent_event_title:
        lines.append(f"Recent: {snap.recent_event_title}")
    if snap.email_themes:
        lines.append(f"Email themes: {', '.join(snap.email_themes[:3])}")
    if snap.topical_affinity:
        lines.append(f"Headspace mode: {snap.topical_affinity}")
    if not calendar_events and not email_threads:
        lines.append("No live Google data yet")
    return lines
