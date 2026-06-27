"""Structured LLM calls via the Gemini Interactions API."""

from __future__ import annotations

import json

from kairos.config import settings
from kairos.llm.client import get_genai_client
from kairos.models.schemas import BookmarkEnrichment, ClusterDigest, ContextSnapshot


def _response_format_for(model: type) -> list[dict]:
    schema = model.model_json_schema()
    return [{"type": "json_schema", "json_schema": {"name": model.__name__, "schema": schema}}]


def enrich_bookmark(raw_text: str, url: str) -> BookmarkEnrichment:
    """Extract bookmark metadata via structured output."""
    client = get_genai_client()
    interaction = client.interactions.create(
        model=settings.gemini_flash_lite_model,
        input=(
            "Analyze this bookmark and return structured metadata.\n\n"
            f"URL: {url}\n\n"
            f"Content:\n{raw_text[:8000]}"
        ),
        system_instruction=(
            "You classify bookmarks for a personal knowledge agent. "
            "energy_cost: 0=quick skim, 1=deep focus. "
            "Extract geo_anchor only for place/product mentions."
        ),
        response_format=_response_format_for(BookmarkEnrichment),
        store=False,
    )
    payload = interaction.output_text or "{}"
    return BookmarkEnrichment.model_validate_json(payload)


def generate_cluster_digest(
    cluster_name: str,
    cluster_summary: str,
    bookmark_snippets: list[str],
    context: ContextSnapshot,
) -> ClusterDigest:
    """Generate digest copy and 'why now' rationale for a cluster."""
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
        response_format=_response_format_for(ClusterDigest),
        store=False,
    )
    payload = interaction.output_text or "{}"
    data = json.loads(payload)
    data.setdefault("cluster_name", cluster_name)
    return ClusterDigest.model_validate(data)
