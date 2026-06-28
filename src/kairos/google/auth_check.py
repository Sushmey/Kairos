"""Pre-flight checks for Google Workspace OAuth."""

from __future__ import annotations

from dataclasses import dataclass, field

from kairos.config import settings
from kairos.google.scopes import HEADSPACE_SCOPES


@dataclass
class GoogleAuthCheckResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _mask(value: str | None) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return f"{value[:2]}...{value[-2:]}"
    return f"{value[:4]}...{value[-4:]}"


def run_auth_check() -> GoogleAuthCheckResult:
    result = GoogleAuthCheckResult(ok=True)
    result.lines.append("Google Workspace pre-flight check")
    result.lines.append("")
    result.lines.append(f"  GOOGLE_CLIENT_ID:       {_mask(settings.google_client_id)}")
    result.lines.append(
        f"  GOOGLE_CLIENT_SECRET:   {'set' if settings.google_client_secret else '(missing)'}"
    )
    result.lines.append(f"  redirect URI:           {settings.google_oauth_redirect_uri}")
    result.lines.append(f"  OAuth timeout:          {settings.google_oauth_timeout_seconds}s")
    result.lines.append(f"  KAIROS_USER_ID:         {_mask(settings.kairos_user_id)}")
    result.lines.append(f"  headspace scopes:       {len(HEADSPACE_SCOPES)} scopes")
    result.lines.append("")

    if not settings.google_client_id or not settings.google_client_secret:
        result.errors.append(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET required — see docs/GOOGLE_WORKSPACE_SETUP.md"
        )
        result.ok = False

    if settings.google_calendar_credentials_path:
        result.warnings.append(
            "GOOGLE_CALENDAR_CREDENTIALS_PATH is deprecated — use connect_google / kairos google connect"
        )

    result.lines.append("Connect (MCP or CLI — loopback callback, not web app):")
    result.lines.append("  MCP:  connect_google() or start_google_connect + wait_google_connect")
    result.lines.append("  CLI:  kairos google connect --write-env")
    result.lines.append("  Then: kairos google verify --user-id <google-sub>")
    result.lines.append("")
    result.lines.append("Register in GCP Desktop OAuth client:")
    result.lines.append(f"  {settings.google_oauth_redirect_uri}")

    result.lines.extend(f"ERROR: {msg}" for msg in result.errors)
    result.lines.extend(f"WARN:  {msg}" for msg in result.warnings)

    if result.errors:
        result.ok = False

    return result
