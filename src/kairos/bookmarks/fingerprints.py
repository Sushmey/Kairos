"""Content fingerprints for incremental enrich / embed."""

from __future__ import annotations

import hashlib
from typing import Any

from kairos.embeddings.encoder import bookmark_embed_text, effective_embedding_model


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def enrich_source_hash(raw_text: str) -> str:
    """Hash raw tweet text — enrichment is stale when this changes."""
    return _digest(raw_text.strip())


def research_source_hash(raw_text: str, url: str, link_content: str = "") -> str:
    """Hash text + url + fetched link body — research stale when any changes."""
    return _digest(f"{url.strip()}:{raw_text.strip()}:{link_content.strip()}")


def embed_fingerprint(doc: dict[str, Any]) -> str:
    """Hash model + embed input — re-embed when text/tags or model changes."""
    text = bookmark_embed_text(doc)
    return _digest(f"{effective_embedding_model()}:{text}")
