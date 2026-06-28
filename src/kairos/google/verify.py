"""Verify Google sensor data and fuse into headspace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kairos.google.credentials import auth_configured_for_env, user_has_google
from kairos.google.headspace_sync import sync_google_headspace


@dataclass
class GoogleVerifyReport:
    ok: bool
    user_id: str | None = None
    calendar_events: list[dict[str, Any]] = field(default_factory=list)
    email_threads: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] | None = None
    moment: str = ""
    ctx_class: str = ""
    issues: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "user_id": self.user_id,
            "issues": self.issues,
            "highlights": self.highlights,
            "calendar_event_count": len(self.calendar_events),
            "email_thread_count": len(self.email_threads),
            "context": self.snapshot,
            "moment_text": self.moment,
            "context_class": self.ctx_class,
        }


async def verify_google_headspace(
    *,
    user_id: str | None = None,
    persist: bool = True,
    location_type: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
    use_env_fallback: bool = False,
) -> GoogleVerifyReport:
    """Fetch Calendar + Gmail for a user, fuse headspace, assess data quality."""
    report = GoogleVerifyReport(ok=False, user_id=user_id)

    if user_id:
        if not await user_has_google(user_id) and not use_env_fallback:
            report.issues.append(
                f"User {user_id} has not connected Google. Run connect_google (MCP) or kairos google connect."
            )
            return report
    elif not use_env_fallback and not auth_configured_for_env():
        report.issues.append(
            "No user_id and no .env tokens. Run connect_google or kairos google connect."
        )
        return report

    if use_env_fallback or not user_id:
        use_env_fallback = True
        persist_id = user_id
    else:
        persist_id = user_id

    result = await sync_google_headspace(
        persist_id,
        persist=persist,
        location_type=location_type,
        lat=lat,
        lng=lng,
        use_env_fallback=use_env_fallback,
    )

    report.ok = bool(result.get("ok"))
    report.issues = list(result.get("issues") or [])
    report.highlights = list(result.get("highlights") or [])
    report.moment = result.get("moment_text") or ""
    report.ctx_class = result.get("context_class") or ""
    report.snapshot = result.get("context")
    report.calendar_events = [{}] * int(result.get("calendar_event_count") or 0)
    report.email_threads = [{}] * int(result.get("email_thread_count") or 0)
    return report
