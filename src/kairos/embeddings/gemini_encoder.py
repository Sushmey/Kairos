"""Gemini Embedding API backend — no local model load."""

from __future__ import annotations

import logging

from google.genai import types

from kairos.config import settings
from kairos.llm.client import get_genai_client

logger = logging.getLogger(__name__)


def _embed_config(*, task_type: str) -> types.EmbedContentConfig:
    return types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=settings.gemini_embedding_dimensions,
    )


def _embed_batch(texts: list[str], *, task_type: str) -> list[list[float]]:
    if not texts:
        return []
    client = get_genai_client()
    response = client.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=texts,
        config=_embed_config(task_type=task_type),
    )
    embeddings = response.embeddings or []
    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"Gemini returned {len(embeddings)} embeddings for {len(texts)} inputs"
        )
    return [list(emb.values) for emb in embeddings]


def encode_documents(texts: list[str]) -> list[list[float]]:
    """Embed bookmark corpus texts via Gemini (RETRIEVAL_DOCUMENT)."""
    batch_size = max(1, settings.embedding_batch_size)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        vectors.extend(_embed_batch(chunk, task_type="RETRIEVAL_DOCUMENT"))
        logger.debug("Gemini embedded batch %s–%s", start, start + len(chunk))
    return vectors


def encode_query(text: str) -> list[float]:
    """Embed a moment/query string (RETRIEVAL_QUERY)."""
    return _embed_batch([text], task_type="RETRIEVAL_QUERY")[0]
