"""Bookmark repository — upsert by x_tweet_id."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncio

from kairos.bookmarks.fingerprints import enrich_source_hash
from kairos.embeddings.encoder import effective_embedding_model
from kairos.db.mongo import get_database
from kairos.models.schemas import BookmarkDocument

COLLECTION = "bookmarks"

DERIVED_FIELDS_ON_TEXT_CHANGE = (
    "embedding",
    "cluster_id",
    "embed_fingerprint",
    "embedding_model",
    "enrich_source_hash",
    "topic_tags",
    "consumption_mode",
    "energy_cost",
    "geo_anchor",
    "perishability",
)


async def ensure_bookmark_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("x_tweet_id", unique=True)
    await db[COLLECTION].create_index("cluster_id")
    await db[COLLECTION].create_index("last_synced_at")


async def get_by_x_tweet_id(x_tweet_id: str) -> dict[str, Any] | None:
    return await get_database()[COLLECTION].find_one({"x_tweet_id": x_tweet_id})


async def count_bookmarks() -> int:
    return await get_database()[COLLECTION].count_documents({})


async def list_bookmarks(
    *,
    limit: int = 20,
    skip: int = 0,
) -> list[dict[str, Any]]:
    """Return bookmarks newest-first by ingested_at, then tweet_created_at."""
    cursor = (
        get_database()[COLLECTION]
        .find({})
        .sort([("ingested_at", -1), ("tweet_created_at", -1)])
        .skip(skip)
        .limit(limit)
    )
    return await cursor.to_list(length=limit)


async def list_all_bookmarks(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Return all bookmarks, optionally capped."""
    cursor = get_database()[COLLECTION].find({}).sort([("ingested_at", -1)])
    if limit is not None:
        cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit or 10_000)


async def count_unclustered_embedded() -> int:
    """Bookmarks with embeddings but no cluster assignment."""
    return await get_database()[COLLECTION].count_documents(
        {
            "embedding": {"$exists": True, "$ne": None},
            "$or": [{"cluster_id": None}, {"cluster_id": {"$exists": False}}],
        }
    )


async def apply_enrichment(x_tweet_id: str, doc: BookmarkDocument) -> bool:
    """Write enrichment fields onto an existing bookmark."""
    now = datetime.now(timezone.utc)
    payload = doc.model_dump(
        exclude_none=True,
        include={
            "topic_tags",
            "consumption_mode",
            "energy_cost",
            "geo_anchor",
            "perishability",
        },
    )
    payload["enrich_source_hash"] = enrich_source_hash(doc.raw_text)
    payload["last_synced_at"] = now
    result = await get_database()[COLLECTION].update_one(
        {"x_tweet_id": x_tweet_id},
        {"$set": payload},
    )
    return result.matched_count > 0


async def apply_enrichments_batch(docs: list[tuple[str, BookmarkDocument]]) -> int:
    """Apply enrichment updates in parallel. Returns count of matched documents."""
    if not docs:
        return 0
    results = await asyncio.gather(*(apply_enrichment(tid, doc) for tid, doc in docs))
    return sum(1 for ok in results if ok)


async def apply_embeddings_batch(updates: list[tuple[str, list[float], str]]) -> int:
    """Bulk-write embeddings with fingerprint + model metadata."""
    if not updates:
        return 0
    from pymongo import UpdateOne

    now = datetime.now(timezone.utc)
    db = get_database()
    ops = [
        UpdateOne(
            {"x_tweet_id": x_tweet_id},
            {
                "$set": {
                    "embedding": embedding,
                    "embed_fingerprint": fingerprint,
                    "embedding_model": effective_embedding_model(),
                    "last_synced_at": now,
                },
                "$unset": {"cluster_id": ""},
            },
        )
        for x_tweet_id, embedding, fingerprint in updates
    ]
    result = await db[COLLECTION].bulk_write(ops, ordered=False)
    return result.matched_count


async def upsert_bookmark(doc: BookmarkDocument) -> str:
    """Upsert bookmark by x_tweet_id. Returns 'inserted' | 'updated' | 'unchanged'."""
    now = datetime.now(timezone.utc)
    payload = doc.model_dump(exclude_none=True, exclude={"id"})
    payload["last_synced_at"] = now
    if doc.consumption_mode is not None or doc.topic_tags:
        payload["enrich_source_hash"] = enrich_source_hash(doc.raw_text)

    existing = await get_by_x_tweet_id(doc.x_tweet_id)
    text_changed = existing and existing.get("raw_text") != doc.raw_text

    if existing and not text_changed and doc.raw_text == existing.get("raw_text") and doc.embedding is None:
        await get_database()[COLLECTION].update_one(
            {"x_tweet_id": doc.x_tweet_id},
            {"$set": {"last_synced_at": now}},
        )
        return "unchanged"

    if existing:
        payload.setdefault("ingested_at", existing.get("ingested_at", now))
        update: dict[str, Any] = {"$set": payload}
        if text_changed:
            update["$unset"] = {field: "" for field in DERIVED_FIELDS_ON_TEXT_CHANGE}
        await get_database()[COLLECTION].update_one({"x_tweet_id": doc.x_tweet_id}, update)
        return "updated"

    payload.setdefault("ingested_at", now)
    payload.setdefault("surface_count", 0)
    await get_database()[COLLECTION].insert_one(payload)
    return "inserted"
