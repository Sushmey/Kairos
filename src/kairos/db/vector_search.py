"""MongoDB Atlas vector search with in-memory cosine fallback."""

from __future__ import annotations

import logging
from typing import Any

from kairos.config import settings
from kairos.db.mongo import get_database
from kairos.embeddings.similarity import cosine_similarity

logger = logging.getLogger(__name__)

CLUSTERS_COLLECTION = "clusters"
BOOKMARKS_COLLECTION = "bookmarks"


async def ensure_vector_indexes() -> None:
    """Best-effort Atlas vector index creation (no-op on local MongoDB)."""
    if not settings.mongodb_vector_search_enabled:
        return
    dims = settings.gemini_embedding_dimensions
    db = get_database()
    for collection, index_name, path in (
        (CLUSTERS_COLLECTION, settings.mongodb_clusters_vector_index, "centroid_embedding"),
        (BOOKMARKS_COLLECTION, settings.mongodb_bookmarks_vector_index, "embedding"),
    ):
        try:
            await db[collection].create_search_index(
                {
                    "name": index_name,
                    "definition": {
                        "mappings": {
                            "dynamic": False,
                            "fields": {
                                path: {
                                    "type": "knnVector",
                                    "dimensions": dims,
                                    "similarity": "cosine",
                                }
                            },
                        }
                    },
                }
            )
            logger.info("Vector search index ensured: %s.%s", collection, index_name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Vector index %s on %s skipped: %s", index_name, collection, exc)


async def search_clusters_by_vector(
    query_vector: list[float],
    *,
    limit: int = 50,
    exclude_cluster_ids: set[str] | None = None,
) -> list[tuple[dict[str, Any], float]] | None:
    """Return ranked (cluster, vector_score) via Atlas $vectorSearch, or None to fallback."""
    if not settings.mongodb_vector_search_enabled:
        return None

    exclude = list(exclude_cluster_ids or [])
    num_candidates = max(limit * 4, settings.vector_search_num_candidates)
    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": settings.mongodb_clusters_vector_index,
                "path": "centroid_embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit + len(exclude),
                **(
                    {"filter": {"cluster_id": {"$nin": exclude}}}
                    if exclude
                    else {}
                ),
            }
        },
        {
            "$project": {
                "cluster_id": 1,
                "name": 1,
                "summary": 1,
                "centroid_embedding": 1,
                "member_count": 1,
                "evergreen": 1,
                "embedding_model": 1,
                "last_updated": 1,
                "vector_score": {"$meta": "vectorSearchScore"},
            }
        },
        {"$limit": limit},
    ]

    try:
        cursor = get_database()[CLUSTERS_COLLECTION].aggregate(pipeline)
        rows = await cursor.to_list(length=limit)
        if not rows:
            return None
        return [(row, float(row.get("vector_score") or 0.0)) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Cluster vector search unavailable, using fallback: %s", exc)
        return None


async def search_bookmarks_by_vector(
    query_vector: list[float],
    *,
    limit: int = 5,
) -> list[tuple[dict[str, Any], float]] | None:
    """Return ranked (bookmark, vector_score) via Atlas $vectorSearch, or None to fallback."""
    if not settings.mongodb_vector_search_enabled:
        return None

    num_candidates = max(limit * 8, settings.vector_search_num_candidates)
    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": settings.mongodb_bookmarks_vector_index,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": num_candidates,
                "limit": limit,
            }
        },
        {
            "$project": {
                "x_tweet_id": 1,
                "url": 1,
                "raw_text": 1,
                "cluster_id": 1,
                "topic_tags": 1,
                "vector_score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        cursor = get_database()[BOOKMARKS_COLLECTION].aggregate(pipeline)
        rows = await cursor.to_list(length=limit)
        if not rows:
            return None
        return [(row, float(row.get("vector_score") or 0.0)) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Bookmark vector search unavailable, using fallback: %s", exc)
        return None


def rank_clusters_in_memory(
    query_vector: list[float],
    clusters: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> list[tuple[dict[str, Any], float]]:
    """Cosine rank clusters already loaded from MongoDB."""
    scored: list[tuple[dict[str, Any], float]] = []
    for cluster in clusters:
        centroid = cluster.get("centroid_embedding")
        if not centroid:
            continue
        score = cosine_similarity(query_vector, centroid)
        scored.append((cluster, score))
    scored.sort(key=lambda row: row[1], reverse=True)
    if limit is not None:
        return scored[:limit]
    return scored
