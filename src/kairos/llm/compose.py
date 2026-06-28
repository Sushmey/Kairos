"""LLM headspace composition and moment-fit checks."""

from __future__ import annotations

import orjson
import logging
from datetime import datetime, timezone
from typing import Any

from kairos.config import settings
from kairos.llm.interactions import create_interaction
from kairos.models.schemas import (
    AttentionCapacity,
    ContextSnapshot,
    HeadspaceEnrichment,
    MomentFitResult,
    TopicalAffinity,
)
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)


def _response_format_for(model: type) -> list[dict]:
    schema = model.model_json_schema()
    fmt: dict = {"type": "object", "properties": schema.get("properties", {})}
    if required := schema.get("required"):
        fmt["required"] = required
    return [fmt]


_HEADSPACE_FORMAT = _response_format_for(HeadspaceEnrichment)
_MOMENT_FIT_FORMAT = _response_format_for(MomentFitResult)


def _truncate_json(payload: Any, *, max_chars: int | None = None) -> str:
    limit = max_chars or settings.intelligence_max_sensor_chars
    text = orjson.dumps(payload, default=str).decode()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _merge_enrichment(
    base: ContextSnapshot,
    enrichment: HeadspaceEnrichment,
) -> ContextSnapshot:
    updates: dict[str, Any] = {}
    if enrichment.topical_affinity:
        updates["topical_affinity"] = enrichment.topical_affinity
    if enrichment.attention_capacity:
        updates["attention_capacity"] = enrichment.attention_capacity
    if enrichment.email_themes:
        updates["email_themes"] = enrichment.email_themes[:8]
    updates["communication_burst"] = enrichment.communication_burst
    if enrichment.moment_narrative.strip():
        updates["moment_narrative"] = enrichment.moment_narrative.strip()
        updates["moment_narrative_at"] = datetime.now(timezone.utc)
    sources = list(base.sensor_sources)
    if "llm_compose" not in sources:
        sources.append("llm_compose")
    updates["sensor_sources"] = sources
    return base.model_copy(update=updates)


def enrich_headspace_from_sensors(
    base: ContextSnapshot,
    *,
    calendar_events: list[dict[str, Any]] | None = None,
    email_threads: list[dict[str, Any]] | None = None,
) -> ContextSnapshot:
    """LLM-enrich a heuristic snapshot using raw Calendar/Gmail payloads."""
    interaction = create_interaction(
        label="headspace-enrich",
        model=settings.gemini_flash_lite_model,
        input=(
            "Interpret this person's current headspace for a bookmark-surfacing agent.\n\n"
            f"Heuristic snapshot:\n{base.model_dump_json()}\n\n"
            f"Calendar events:\n{_truncate_json(calendar_events or [])}\n\n"
            f"Email threads:\n{_truncate_json(email_threads or [])}\n\n"
            "Return topical_affinity (work|explore|recovery|triage), attention_capacity "
            "(high|medium|low|none), refined email_themes (short topic labels), "
            "communication_burst, and moment_narrative: 2-4 sentences describing what "
            "kind of cognitive moment this is — suitable as a semantic search query for "
            "matching saved bookmark clusters."
        ),
        system_instruction=(
            "You fuse calendar, email, and location signals into a headspace reading. "
            "Prefer triage after meetings with email backlog; explore at cafe; recovery "
            "post-meeting; work when preparing for upcoming events. "
            "attention_capacity none when gaps are tight or fatigue is high."
        ),
        response_format=_HEADSPACE_FORMAT,
        store=False,
    )
    payload = interaction.output_text or "{}"
    enrichment = HeadspaceEnrichment.model_validate_json(payload)
    result = _merge_enrichment(base, enrichment)
    event_bus.emit(
        "intelligence",
        f"Enriched headspace from calendar and email — attention {result.attention_capacity}, "
        f"topical affinity {result.topical_affinity}.",
        topical_affinity=result.topical_affinity,
        attention_capacity=result.attention_capacity,
    )
    return result


def enrich_context_narrative(context: ContextSnapshot) -> ContextSnapshot:
    """LLM-compose moment_narrative from an existing snapshot (heartbeat tick path)."""
    if context.moment_narrative:
        return context
    interaction = create_interaction(
        label="moment-narrative",
        model=settings.gemini_flash_lite_model,
        input=(
            "Write a moment_narrative for semantic cluster matching.\n\n"
            f"Context snapshot:\n{context.model_dump_json()}\n\n"
            "Return enriched topical_affinity, attention_capacity, email_themes, "
            "communication_burst, and moment_narrative (2-4 sentences)."
        ),
        system_instruction=(
            "Compose a vivid but factual headspace narrative. This text will be embedded "
            "and matched against bookmark topic clusters — focus on moment, capacity, and themes."
        ),
        response_format=_HEADSPACE_FORMAT,
        store=False,
    )
    payload = interaction.output_text or "{}"
    enrichment = HeadspaceEnrichment.model_validate_json(payload)
    result = _merge_enrichment(context, enrichment)
    snippet = result.moment_narrative.strip()
    if len(snippet) > 160:
        snippet = snippet[:157] + "…"
    event_bus.emit(
        "intelligence",
        f"Composed moment narrative for embedding: \"{snippet}\"",
        preview=result.moment_narrative[:200],
    )
    return result


def check_moment_fit(
    context: ContextSnapshot,
    *,
    cluster_name: str,
    cluster_summary: str,
    bookmark_snippets: list[str],
) -> MomentFitResult:
    """LLM gate: is this cluster worth interrupting for right now?"""
    snippets = "\n".join(f"- {s[:200]}" for s in bookmark_snippets[:5])
    interaction = create_interaction(
        label="moment-fit",
        model=settings.gemini_flash_lite_model,
        input=(
            f"Cluster: {cluster_name}\n"
            f"Summary: {cluster_summary}\n\n"
            f"Bookmarks:\n{snippets or '(none)'}\n\n"
            f"User moment:\n{context.model_dump_json()}\n\n"
            "Does this cluster genuinely fit the user's current headspace? "
            "fit=false if the interrupt would feel random, poorly timed, or low-value."
        ),
        system_instruction=(
            "You are a moment-fit judge for a contextual bandit. Be conservative — "
            "false positives (bad interrupts) are worse than silence. "
            "Return fit, reason, and confidence 0-1."
        ),
        response_format=_MOMENT_FIT_FORMAT,
        store=False,
    )
    payload = interaction.output_text or '{"fit": true, "reason": "fallback", "confidence": 0.5}'
    result = MomentFitResult.model_validate_json(payload)
    verdict = "fits" if result.fit else "does not fit"
    event_bus.emit(
        "intelligence",
        f"Moment-fit judge: cluster {verdict} this headspace — {result.reason} "
        f"(confidence {result.confidence:.0%}).",
        fit=result.fit,
        reason=result.reason,
        confidence=result.confidence,
    )
    return result
