"""Pre-flight checks for X OAuth configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from kairos.config import settings
from kairos.ingest.x.oauth import DEFAULT_SCOPES, build_authorize_url, generate_pkce_pair, generate_state

# Common redirect URIs — X requires exact match with Developer Portal allowlist.
SUGGESTED_CALLBACKS = (
    "http://127.0.0.1:8765/callback",
    "http://localhost:8765/callback",
)

MINIMAL_SCOPES = "users.read tweet.read offline.access"


@dataclass
class AuthCheckResult:
    ok: bool
    lines: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _mask_client_id(client_id: str | None) -> str:
    if not client_id:
        return "(not set)"
    if len(client_id) <= 8:
        return f"{client_id[:2]}...{client_id[-2:]}"
    return f"{client_id[:4]}...{client_id[-4:]}"


def run_auth_check(*, redirect_uri: str | None = None, scopes: str | None = None) -> AuthCheckResult:
    """Validate local OAuth config and print a Developer Portal checklist."""
    result = AuthCheckResult(ok=True)
    redirect = redirect_uri or settings.x_oauth_redirect_uri
    scope = scopes or settings.x_oauth_scopes or DEFAULT_SCOPES
    parsed = urlparse(redirect)

    result.lines.append("X OAuth pre-flight check")
    result.lines.append("")
    result.lines.append(f"  X_CLIENT_ID:          {_mask_client_id(settings.x_client_id)}")
    result.lines.append(f"  X_CLIENT_SECRET:      {'set' if settings.x_client_secret else '(empty — OK for Native/PKCE app)'}")
    result.lines.append(f"  redirect_uri:         {redirect}")
    result.lines.append(f"  scopes:               {scope}")
    result.lines.append("")

    if not settings.x_client_id:
        result.errors.append("X_CLIENT_ID is missing in .env")
        result.ok = False

    if "localhost" in redirect and "127.0.0.1" not in redirect:
        result.warnings.append(
            "redirect_uri uses localhost — register http://localhost:8765/callback exactly "
            "(NOT 127.0.0.1; they are different strings to X)"
        )

    if "127.0.0.1" in redirect:
        result.warnings.append(
            "redirect_uri uses 127.0.0.1 — register http://127.0.0.1:8765/callback exactly "
            "(NOT localhost)"
        )

    if parsed.path != "/callback":
        result.warnings.append(
            f"redirect path is {parsed.path!r} — must match Developer Portal callback path exactly"
        )

    if "bookmark.read" in scope:
        result.warnings.append(
            "bookmark.read requires a paid X API tier (Basic+). If auth fails, retry with:\n"
            "    kairos x auth --minimal-scopes"
        )

    if settings.x_client_secret:
        result.warnings.append(
            "X_CLIENT_SECRET is set — use Web App / confidential client settings in Developer Portal"
        )
    else:
        result.warnings.append(
            "No X_CLIENT_SECRET — use Native App (public client + PKCE) in Developer Portal"
        )

    result.lines.append("Developer Portal checklist (console.x.com → your app → User authentication settings):")
    result.lines.append("  1. Enable OAuth 2.0")
    result.lines.append("  2. App type: Native App (public) OR Web App (confidential)")
    result.lines.append(f"  3. Callback URI / Redirect URL — add EXACTLY: {redirect}")
    result.lines.append(f"  4. Website URL — set to: {parsed.scheme}://{parsed.netloc}")
    result.lines.append("  5. Save settings and wait ~1 minute for propagation")
    result.lines.append("")
    result.lines.append("Before authorizing:")
    result.lines.append("  • Log into https://x.com in the SAME browser first (known X OAuth quirk)")
    result.lines.append("  • Then run: kairos x auth")
    result.lines.append("")
    result.lines.append("If you still see 'Something went wrong':")
    result.lines.append("  • Callback URL mismatch is the #1 cause — compare character-for-character")
    result.lines.append("  • Try --minimal-scopes to rule out bookmark.read tier issues")
    result.lines.append("  • Try alternate callback if registered:")
    for uri in SUGGESTED_CALLBACKS:
        if uri != redirect:
            result.lines.append(f"      kairos x auth --redirect-uri {uri}")

    if settings.x_client_id:
        verifier, challenge = generate_pkce_pair()
        sample_url = build_authorize_url(
            client_id=settings.x_client_id,
            redirect_uri=redirect,
            scope=scope,
            state=generate_state(),
            code_challenge=challenge,
        )
        result.lines.append("")
        result.lines.append("Sample authorize URL (PKCE params rotate each run):")
        result.lines.append(f"  {sample_url[:120]}...")

    result.lines.extend(f"ERROR: {msg}" for msg in result.errors)
    result.lines.extend(f"WARN:  {msg}" for msg in result.warnings)

    if result.errors:
        result.ok = False

    return result
