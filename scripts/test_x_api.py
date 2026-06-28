#!/usr/bin/env python3
"""Smoke test for X API OAuth user-context connectivity."""

from __future__ import annotations

import asyncio
import orjson
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root before kairos settings are imported.
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from kairos.config import settings  # noqa: E402
from kairos.ingest.x.client import XApiClient, XApiError  # noqa: E402
from kairos.ingest.x.normalize import extract_tweet_text  # noqa: E402

_NUMERIC_ID = re.compile(r"^[0-9]{1,19}$")


def _mask(value: str | None, visible: int = 4) -> str:
    if not value:
        return "(not set)"
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"


def _print_config() -> None:
    print("X API connection test")
    print(f"  .env loaded from: {ROOT / '.env'}")
    print(f"  base URL:         {settings.x_api_base_url}")
    print(f"  access token:     {_mask(settings.x_access_token)}")
    uid = settings.x_user_id
    if uid and not _NUMERIC_ID.match(uid):
        print(f"  user id (env):    {uid!r}  ⚠ expected numeric id, not @handle")
    else:
        print(f"  user id (env):    {uid or '(will resolve via /2/users/me)'}")


async def main() -> int:
    _print_config()

    if not settings.x_access_token:
        print("\n✗ X_ACCESS_TOKEN is missing. Run: kairos x auth", file=sys.stderr)
        return 1

    client = XApiClient()

    try:
        me = await client.get_me()
        user = me["data"]
        print("\n✓ GET /2/users/me")
        print(f"  id:       {user['id']}")
        print(f"  username: @{user.get('username', '?')}")
        print(f"  name:     {user.get('name', '?')}")

        uid = user["id"]
        if settings.x_user_id and settings.x_user_id != uid and _NUMERIC_ID.match(settings.x_user_id):
            print(f"  note: env X_USER_ID ({settings.x_user_id}) differs from token holder ({uid})")

        page = await anext(client.iter_bookmarks(user_id=uid, max_results=5, max_pages=1))

        meta = page.get("meta") or {}
        tweets = page.get("data") or []
        print("\n✓ GET /2/users/{id}/bookmarks (1 page, max_results=5)")
        print(f"  result_count: {meta.get('result_count', len(tweets))}")
        print(f"  has_next:     {bool(meta.get('next_token'))}")

        if tweets:
            sample = tweets[0]
            preview = extract_tweet_text(sample).replace("\n", " ")[:120]
            print(f"  sample id:    {sample.get('id')}")
            print(f"  sample text:  {preview!r}")
        else:
            print("  (no bookmarks on this page)")

        print("\nX API connection OK")
        return 0

    except XApiError as exc:
        print(f"\n✗ X API error: {exc}", file=sys.stderr)
        if exc.status_code:
            print(f"  status: {exc.status_code}", file=sys.stderr)
        if exc.status_code == 401:
            print(
                "  hint: token expired or invalid — run: kairos x refresh\n"
                "        or re-authorize: kairos x auth\n"
                "        required scopes: bookmark.read tweet.read users.read offline.access",
                file=sys.stderr,
            )
        if exc.payload:
            print(orjson.dumps(exc.payload, option=orjson.OPT_INDENT_2).decode()[:2000], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
