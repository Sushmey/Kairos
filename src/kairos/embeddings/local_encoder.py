"""Local sentence-transformers embedding backend."""

from __future__ import annotations

from kairos.config import settings

_encoder = None


def get_encoder():
    """Lazy-load sentence-transformers model."""
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer

        _encoder = SentenceTransformer(settings.embedding_model)
    return _encoder


def encode_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_encoder()
    vectors = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [vector.tolist() for vector in vectors]


def encode_query(text: str) -> list[float]:
    model_name = settings.embedding_model.lower()
    if "bge" in model_name:
        prefixed = f"Represent this sentence for searching relevant passages: {text}"
    elif "e5" in model_name:
        prefixed = f"query: {text}"
    else:
        prefixed = text
    model = get_encoder()
    vector = model.encode(
        prefixed,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vector.tolist()
