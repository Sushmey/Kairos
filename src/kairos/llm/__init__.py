"""LLM layer — Interactions API for batch / structured calls."""

from kairos.llm.client import get_genai_client
from kairos.llm.compose import check_moment_fit, enrich_context_narrative, enrich_headspace_from_sensors
from kairos.llm.enrichment import enrich_bookmark
from kairos.llm.generation import generate_cluster_digest

__all__ = [
    "enrich_bookmark",
    "generate_cluster_digest",
    "get_genai_client",
]
