"""Kairos tools — thin wrappers over policy core (usable by Antigravity + MCP)."""

from __future__ import annotations

import asyncio
from typing import Any

from kairos.core.context import read_context
from kairos.core.heartbeat import heartbeat_service
from kairos.db.clusters import list_clusters
from kairos.db.mongo import close_mongo
from kairos.embeddings.encoder import encode_query
from kairos.models.schemas import DeliveryMode, FeedbackAction
from kairos.observability.bus import event_bus


def get_current_context() -> dict[str, Any]:
    """Read the live headspace vector: calendar, location, time, attention capacity."""
    return read_context().model_dump()


def get_relevant_bookmarks(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search over the bookmark index.

    Args:
        query: Natural language search query.
        limit: Maximum bookmarks to return.
    """
    # TODO: wire MongoDB $vectorSearch
    event_bus.emit(
        "search",
        f"Semantic search: {query!r}",
        query=query,
        limit=limit,
        results=0,
    )
    return []


async def _cluster_for_topic(topic: str) -> dict[str, Any] | None:
    from kairos.core.ranking import _cosine

    clusters = await list_clusters()
    clusters = [c for c in clusters if c.get("centroid_embedding")]
    if not clusters:
        return None
    vector = encode_query(topic)
    best: dict[str, Any] | None = None
    best_score = -1.0
    for cluster in clusters:
        score = _cosine(vector, cluster["centroid_embedding"])
        if score > best_score:
            best_score = score
            best = cluster
    return best


def get_cluster_summary(topic: str) -> dict[str, Any] | None:
    """Return the cluster closest to topic with its generated summary.

    Args:
        topic: Topic label or natural language description.
    """
    async def _run() -> dict[str, Any] | None:
        try:
            cluster = await _cluster_for_topic(topic)
            if not cluster:
                return None
            return {
                "cluster_id": cluster.get("cluster_id"),
                "name": cluster.get("name"),
                "summary": cluster.get("summary"),
                "member_count": cluster.get("member_count"),
            }
        finally:
            await close_mongo()

    result = asyncio.run(_run())
    event_bus.emit("cluster", f"Lookup cluster for {topic!r}", topic=topic, found=bool(result))
    return result


def run_heartbeat(
    delivery: DeliveryMode = "auto",
    context_override: str | None = None,
) -> dict[str, Any]:
    """Run one heartbeat: context → rank → gate → publish to configured targets.

    Returns KAIROS_OK when silent or SURFACE with digest + host delivery hints.
    MCP clients should render delivery.rendered_markdown in chat on SURFACE.

    Args:
        delivery: auto (configured adapters), return_only (no side effects), none.
        context_override: Optional free-text context hint for demo overrides.
    """
    result = asyncio.run(
        heartbeat_service.run(delivery=delivery, context_override=context_override)
    )
    return result.model_dump()


async def run_heartbeat_async(
    delivery: DeliveryMode = "auto",
    context_override: str | None = None,
) -> dict[str, Any]:
    """Async heartbeat for harness and HTTP handlers."""
    result = await heartbeat_service.run(delivery=delivery, context_override=context_override)
    return result.model_dump()


def record_feedback(
    notification_id: str,
    action: FeedbackAction,
    url: str | None = None,
) -> dict[str, str]:
    """Record user feedback on a surfaced digest (any host: web, MCP chat, etc.)."""
    return asyncio.run(
        heartbeat_service.record_feedback(notification_id, action, url=url)
    )


async def record_feedback_async(
    notification_id: str,
    action: FeedbackAction,
    url: str | None = None,
) -> dict:
    return await heartbeat_service.record_feedback(notification_id, action, url=url)


def add_bookmark(url: str, notes: str = "") -> dict[str, str]:
    """Ingest a new bookmark into the pipeline.

    Args:
        url: Bookmark URL to ingest.
        notes: Optional user notes.
    """
    # TODO: wire ingest + LLM enrichment
    event_bus.emit("ingest", f"Ingest bookmark {url}", url=url, notes=notes)
    return {"status": "stub", "url": url}


# Query + heartbeat tools for Antigravity harness (no direct OS delivery tool)
ALL_TOOLS = [
    get_current_context,
    get_relevant_bookmarks,
    get_cluster_summary,
    run_heartbeat,
    record_feedback,
    add_bookmark,
]
