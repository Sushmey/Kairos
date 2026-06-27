"""Interactions API client for structured LLM workloads."""

from google import genai

from kairos.config import settings

_client: genai.Client | None = None


def get_genai_client() -> genai.Client:
    """Return a shared Gemini Interactions API client."""
    global _client
    if _client is None:
        kwargs: dict = {}
        if settings.gemini_api_key:
            kwargs["api_key"] = settings.gemini_api_key
        _client = genai.Client(**kwargs)
    return _client
