"""Structured LLM calls via the Gemini Interactions API."""

from __future__ import annotations

import json

from kairos.config import settings
from kairos.llm.client import get_genai_client
from kairos.llm.grounding import parse_grounded_interaction
from kairos.models.schemas import BookmarkEnrichment, ClusterDigest, ClusterDigestCore, ContextSnapshot


def _response_format_for(model: type) -> list[dict]:
    schema = model.model_json_schema()
    fmt: dict = {"type": "object", "properties": schema.get("properties", {})}
    if required := schema.get("required"):
        fmt["required"] = required
    return [fmt]


_BOOKMARK_ENRICHMENT_FORMAT = _response_format_for(BookmarkEnrichment)


def enrich_bookmark(raw_text: str, url: str) -> BookmarkEnrichment:
    """Extract bookmark metadata via structured output."""
    client = get_genai_client()
    max_chars = settings.enrich_max_input_chars
    interaction = client.interactions.create(
        model=settings.gemini_flash_lite_model,
        input=(
            "Classify this bookmark.\n\n"
            f"URL: {url}\n\n"
            f"Content:\n{raw_text[:max_chars]}"
        ),
        system_instruction=(
            "Classify bookmarks for a personal knowledge agent. "
            "energy_cost: 0=quick skim, 1=deep focus. "
            "geo_anchor only for explicit place/product mentions."
        ),
        response_format=_BOOKMARK_ENRICHMENT_FORMAT,
        store=False,
    )
    payload = interaction.output_text or "{}"
    return BookmarkEnrichment.model_validate_json(payload)


def _structured_cluster_digest(
    cluster_id: str,
    cluster_name: str,
    cluster_summary: str,
    bookmark_snippets: list[str],
    context: ContextSnapshot,
    member_count: int,
) -> ClusterDigest:
    """Core digest fields from bookmarks + context (no web search)."""
    client = get_genai_client()
    context_json = context.model_dump_json()
    snippets = "\n".join(f"- {s[:300]}" for s in bookmark_snippets[:8])

    interaction = client.interactions.create(
        model=settings.gemini_model,
        input=(
            f"Cluster: {cluster_name}\n"
            f"Summary: {cluster_summary}\n\n"
            f"Bookmarks:\n{snippets}\n\n"
            f"Context:\n{context_json}"
        ),
        system_instruction=(
            "Write a cluster digest for surfacing via web inbox or host agent chat. "
            "why_now: one line explaining timing fit (gap, location, calendar). "
            "links: up to 5 entries with url placeholder '#', label, consumption_mode."
        ),
        response_format=_response_format_for(ClusterDigestCore),
        store=False,
    )
    payload = interaction.output_text or "{}"
    data = json.loads(payload)
    data.setdefault("cluster_id", cluster_id)
    data.setdefault("cluster_name", cluster_name)
    data.setdefault("member_count", member_count)
    return ClusterDigest.model_validate(data)


def _ground_digest_with_search(
    digest: ClusterDigest,
    context: ContextSnapshot,
    bookmark_snippets: list[str],
) -> ClusterDigest:
    """Enrich digest with timely web context via Google Search grounding."""
    client = get_genai_client()
    snippets = "\n".join(f"- {s[:200]}" for s in bookmark_snippets[:5])
    context_bits = [
        f"location={context.location_type}",
        f"calendar_gap_minutes={context.calendar_gap_minutes}",
    ]
    if context.upcoming_event_title:
        context_bits.append(f"upcoming_event={context.upcoming_event_title}")
    if context.recent_event_title:
        context_bits.append(f"recent_event={context.recent_event_title}")

    interaction = client.interactions.create(
        model=settings.gemini_model,
        input=(
            f"Cluster topic: {digest.cluster_name}\n"
            f"Digest summary: {digest.summary}\n"
            f"Why now (draft): {digest.why_now}\n\n"
            f"Saved bookmarks:\n{snippets or '(none)'}\n\n"
            f"User moment: {', '.join(context_bits)}\n\n"
            "Search the web for timely context that connects this cluster to the user's "
            "current moment. Write 2-3 sentences on what's happening in this topic space "
            "that makes revisiting these bookmarks worthwhile now. "
            "Do not list the bookmarks again."
        ),
        system_instruction=(
            "You enrich a personal bookmark digest with grounded, current web context. "
            "Be concise and factual. Prefer recent developments over generic background."
        ),
        tools=[{"type": "google_search"}],
        store=False,
    )
    grounded = parse_grounded_interaction(interaction)
    if not grounded.text:
        return digest

    return digest.model_copy(
        update={
            "web_context": grounded.text,
            "citations": grounded.citations,
        }
    )


def generate_cluster_digest(
    cluster_id: str,
    cluster_name: str,
    cluster_summary: str,
    bookmark_snippets: list[str],
    context: ContextSnapshot,
    *,
    member_count: int = 0,
) -> ClusterDigest:
    """Generate digest copy, optionally enriched with Google Search grounding."""
    digest = _structured_cluster_digest(
        cluster_id,
        cluster_name,
        cluster_summary,
        bookmark_snippets,
        context,
        member_count,
    )
    if settings.digest_use_google_search:
        digest = _ground_digest_with_search(digest, context, bookmark_snippets)
    return digest
