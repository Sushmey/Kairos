"""Google OAuth scopes for Kairos headspace sensors."""

from __future__ import annotations

# Calendar — matches Google Workspace Calendar MCP read scopes
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
]

# Gmail — read-only for topical affinity / communication burst
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

# Headspace MVP: calendar + gmail
HEADSPACE_SCOPES = CALENDAR_SCOPES + GMAIL_SCOPES

# Optional: Drive read for doc context (future)
DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
]

ALL_WORKSPACE_SCOPES = HEADSPACE_SCOPES + DRIVE_SCOPES
