"""Normalize X API tweet payloads into BookmarkDocument."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.models.schemas import BookmarkDocument


def _parse_twitter_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    # X returns ISO-8601, e.g. 2021-01-06T18:40:40.000Z
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _author_lookup(includes: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    users = (includes or {}).get("users") or []
    return {u["id"]: u for u in users if "id" in u}


def _referenced_lookup(includes: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    tweets = (includes or {}).get("tweets") or []
    return {t["id"]: t for t in tweets if "id" in t}


def extract_tweet_text(tweet: dict[str, Any]) -> str:
    note = tweet.get("note_tweet") or {}
    if isinstance(note, dict) and note.get("text"):
        return note["text"]
    return tweet.get("text") or ""


def extract_primary_url(tweet: dict[str, Any]) -> str:
    entities = tweet.get("entities") or {}
    urls = entities.get("urls") or []
    for entry in urls:
        expanded = entry.get("expanded_url") or entry.get("unwound_url")
        if expanded:
            return expanded
    tweet_id = tweet.get("id")
    if tweet_id:
        return f"https://x.com/i/web/status/{tweet_id}"
    return ""


def normalize_bookmark(
    tweet: dict[str, Any],
    includes: dict[str, Any] | None = None,
) -> BookmarkDocument:
    """Map one bookmarked tweet + includes to a BookmarkDocument."""
    x_tweet_id = str(tweet["id"])
    authors = _author_lookup(includes)
    author_id = str(tweet.get("author_id") or "")
    author = authors.get(author_id, {})
    referenced = _referenced_lookup(includes)

    referenced_tweets: list[dict[str, Any]] = []
    for ref in tweet.get("referenced_tweets") or []:
        ref_id = ref.get("id")
        ref_type = ref.get("type")
        ref_tweet = referenced.get(ref_id, {"id": ref_id})
        referenced_tweets.append(
            {
                "type": ref_type,
                "id": ref_id,
                "text": extract_tweet_text(ref_tweet)[:500],
            }
        )

    return BookmarkDocument(
        x_tweet_id=x_tweet_id,
        url=extract_primary_url(tweet),
        raw_text=extract_tweet_text(tweet),
        author_id=author_id or None,
        author_username=author.get("username"),
        tweet_created_at=_parse_twitter_datetime(tweet.get("created_at")),
        context_annotations=list(tweet.get("context_annotations") or []),
        referenced_tweets=referenced_tweets,
    )
