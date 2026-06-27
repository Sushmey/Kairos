"""Kairos custom tools for the Antigravity agent harness."""

from __future__ import annotations

from typing import Any

from kairos.models.schemas import ContextSnapshot, SurfaceDecision
from kairos.observability.bus import event_bus


def get_current_context() -> dict[str, Any]:
    """Read the live headspace vector: calendar, location, time, attention capacity.

    Returns a ContextSnapshot-shaped dict. Stub until context sensor is wired.
    """
    # TODO: wire Google Calendar poller + location toggle
    ctx = ContextSnapshot(
        calendar_gap_minutes=90,
        meeting_density_today=0.3,
        location_type="cafe",
        surfaces_today=1,
    )
    event_bus.emit("context", "Read current headspace", context=ctx.model_dump())
    return ctx.model_dump()


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


def get_cluster_summary(topic: str) -> dict[str, Any] | None:
    """Return the cluster closest to topic with its generated summary.

    Args:
        topic: Topic label or natural language description.
    """
    # TODO: wire clusters collection
    event_bus.emit("cluster", f"Lookup cluster for {topic!r}", topic=topic)
    return None


def surface_now(context_override: str | None = None) -> dict[str, Any]:
    """Run the full ranking pipeline against current context.

    Applies feasibility filter, vector search, bandit adjustment, and interrupt gate.
    Returns a SurfaceDecision. Silence (should_surface=false) is valid.

    Args:
        context_override: Optional free-text context hint for demo overrides.
    """
    ctx = ContextSnapshot.model_validate(get_current_context())
    if context_override:
        event_bus.emit("context_override", context_override)

    # TODO: wire ranking pipeline (steps 1–4 from PLAN.md)
    decision = SurfaceDecision(
        should_surface=False,
        gate_reasons={
            "daily_budget": True,
            "calendar_gap": ctx.calendar_gap_minutes > 30,
            "min_gap": True,
            "score_threshold": False,
        },
        context=ctx,
    )
    event_bus.emit(
        "ranking",
        "Ranking pipeline complete",
        should_surface=decision.should_surface,
        gate_reasons=decision.gate_reasons,
    )
    return decision.model_dump()


def deliver_notification(digest_json: str) -> dict[str, str]:
    """Send a macOS notification with the cluster digest.

    Args:
        digest_json: JSON-serialized ClusterDigest from surface_now.
    """
    # TODO: wire terminal-notifier
    event_bus.emit("notification", "Notification delivery stub", digest=digest_json[:200])
    return {"status": "stub", "message": "terminal-notifier not wired yet"}


def add_bookmark(url: str, notes: str = "") -> dict[str, str]:
    """Ingest a new bookmark into the pipeline.

    Args:
        url: Bookmark URL to ingest.
        notes: Optional user notes.
    """
    # TODO: wire ingest + LLM enrichment
    event_bus.emit("ingest", f"Ingest bookmark {url}", url=url, notes=notes)
    return {"status": "stub", "url": url}


ALL_TOOLS = [
    get_current_context,
    get_relevant_bookmarks,
    get_cluster_summary,
    surface_now,
    deliver_notification,
    add_bookmark,
]
