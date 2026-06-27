"""Embedding encoder — dispatches to local or Gemini API backend."""

from __future__ import annotations

from typing import Any

from kairos.config import settings


def effective_embedding_model() -> str:
    """Model id persisted on bookmark docs (includes dims for API backends)."""
    if settings.embedding_backend == "gemini":
        return f"{settings.gemini_embedding_model}@{settings.gemini_embedding_dimensions}"
    return settings.embedding_model


def bookmark_embed_text(doc: dict[str, Any]) -> str:
    """Compose embeddable text from enrichment + raw tweet body."""
    tags = " ".join(doc.get("topic_tags") or [])
    body = (doc.get("raw_text") or "").strip()
    combined = f"{tags} {body}".strip() if tags else body
    return combined[: settings.embedding_max_input_chars]


def encode_documents(texts: list[str]) -> list[list[float]]:
    if settings.embedding_backend == "gemini":
        from kairos.embeddings.gemini_encoder import encode_documents as _encode

        return _encode(texts)
    from kairos.embeddings.local_encoder import encode_documents as _encode

    return _encode(texts)


def encode_query(text: str) -> list[float]:
    if settings.embedding_backend == "gemini":
        from kairos.embeddings.gemini_encoder import encode_query as _encode

        return _encode(text)
    from kairos.embeddings.local_encoder import encode_query as _encode

    return _encode(text)
