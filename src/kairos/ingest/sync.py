"""X API → MongoDB bookmark sync orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from kairos.db.bookmarks import ensure_bookmark_indexes, get_by_x_tweet_id, upsert_bookmark
from kairos.db.mongo import close_mongo
from kairos.ingest.enrich import enrich_bookmark_documents
from kairos.ingest.x.client import XApiClient, XApiError
from kairos.ingest.x.normalize import normalize_bookmark
from kairos.models.schemas import BookmarkDocument

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    enriched: int = 0
    errors: list[str] = field(default_factory=list)


async def sync_bookmarks_from_x(
    *,
    max_pages: int | None = None,
    enrich: bool = True,
    enrich_existing: bool = False,
    enrich_concurrency: int | None = None,
) -> SyncResult:
    """Paginate X bookmarks, normalize, optionally enrich, upsert to MongoDB."""
    result = SyncResult()
    client = XApiClient()

    await ensure_bookmark_indexes()

    try:
        async for page in client.iter_bookmarks(max_pages=max_pages):
            tweets = page.get("data") or []
            includes = page.get("includes") or {}

            page_docs: list[BookmarkDocument] = []
            page_meta: list[tuple[BookmarkDocument, bool]] = []

            for tweet in tweets:
                result.fetched += 1
                try:
                    doc = normalize_bookmark(tweet, includes)
                    existing = await get_by_x_tweet_id(doc.x_tweet_id)
                    text_changed = not existing or existing.get("raw_text") != doc.raw_text
                    needs_enrich = enrich and (not existing or text_changed or enrich_existing)
                    page_docs.append(doc)
                    page_meta.append((doc, needs_enrich and bool(doc.raw_text)))
                except Exception as exc:  # noqa: BLE001 — collect per-tweet errors, continue sync
                    msg = f"tweet {tweet.get('id')}: {exc}"
                    logger.exception("Failed to normalize bookmark tweet %s", tweet.get("id"))
                    result.errors.append(msg)

            to_enrich = [doc for doc, needs in page_meta if needs]
            if to_enrich:
                enriched_docs, enrich_errors, enriched_count = await enrich_bookmark_documents(
                    to_enrich,
                    concurrency=enrich_concurrency,
                )
                result.enriched += enriched_count
                result.errors.extend(enrich_errors)
                enriched_by_id = {doc.x_tweet_id: doc for doc in enriched_docs}
                page_docs = [enriched_by_id.get(doc.x_tweet_id, doc) for doc in page_docs]

            for doc in page_docs:
                try:
                    status = await upsert_bookmark(doc)
                    if status == "inserted":
                        result.inserted += 1
                    elif status == "updated":
                        result.updated += 1
                    else:
                        result.unchanged += 1
                except Exception as exc:  # noqa: BLE001 — collect per-tweet errors, continue sync
                    msg = f"tweet {doc.x_tweet_id}: {exc}"
                    logger.exception("Failed to upsert bookmark %s", doc.x_tweet_id)
                    result.errors.append(msg)
    finally:
        await close_mongo()

    return result


async def fetch_x_user_id() -> str:
    """Resolve authenticated user id via GET /2/users/me."""
    client = XApiClient()
    payload = await client.get_me()
    return payload["data"]["id"]
