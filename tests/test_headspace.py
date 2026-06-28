"""Tests for HeadspaceComposer fusion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.core.headspace import fuse_headspace, parse_calendar_events
from kairos.core.moment import context_class, moment_text


def test_parse_calendar_events_gap_and_upcoming():
    now = datetime(2026, 6, 27, 14, 0, tzinfo=timezone.utc)
    events = [
        {
            "summary": "Architecture review",
            "start": {"dateTime": (now + timedelta(minutes=45)).isoformat()},
            "end": {"dateTime": (now + timedelta(minutes=105)).isoformat()},
        },
        {
            "summary": "Standup",
            "start": {"dateTime": (now - timedelta(minutes=30)).isoformat()},
            "end": {"dateTime": (now - timedelta(minutes=15)).isoformat()},
        },
    ]
    parsed = parse_calendar_events(events, now=now)
    assert parsed["calendar_gap_minutes"] == 45
    assert parsed["upcoming_event_title"] == "Architecture review"
    assert parsed["recent_event_title"] == "Standup"
    assert parsed["post_meeting_minutes"] == 15


def test_fuse_headspace_email_and_location():
    now = datetime(2026, 6, 27, 10, 0, tzinfo=timezone.utc)
    snapshot = fuse_headspace(
        calendar_events=[
            {
                "summary": "Investor call",
                "start": {"dateTime": (now + timedelta(hours=2)).isoformat()},
                "end": {"dateTime": (now + timedelta(hours=3)).isoformat()},
            }
        ],
        email_themes=["Q4 planning", "Fundraising deck"],
        location_type="desk",
        now=now,
    )
    assert snapshot.location_type == "desk"
    assert snapshot.email_themes == ["Q4 planning", "Fundraising deck"]
    assert snapshot.topical_affinity == "work"
    assert "calendar" in snapshot.sensor_sources
    assert "email" in snapshot.sensor_sources


def test_moment_text_includes_fused_signals():
    snapshot = fuse_headspace(
        location_type="cafe",
        calendar_gap_minutes=90,
        email_themes=["AI safety"],
        now=datetime(2026, 6, 27, 15, 0, tzinfo=timezone.utc),
    )
    text = moment_text(snapshot)
    assert "cafe" in text
    assert "AI safety" in text
    assert context_class(snapshot).startswith("cafe_long_gap")
