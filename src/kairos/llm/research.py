"""Upfront web research on a bookmark via Gemini Google Search grounding.

One grounded call retrieves current web context and validation, then a lenient
parse extracts summary / signal / status. Sources come from grounding citations.
Runs at enrich time (kairos bookmarks research), not in the live heartbeat path.
"""

from __future__ import annotations

import logging
import re

from kairos.bookmarks.urls import is_bare_url
from kairos.config import settings
from kairos.llm.grounding import parse_grounded_interaction
from kairos.llm.interactions import create_interaction
from kairos.models.schemas import BookmarkResearch, RelevanceStatus

logger = logging.getLogger(__name__)

_VALID_STATUS: set[str] = {"current", "dated", "stale", "unknown"}

_SYSTEM = (
    "You pre-research a saved bookmark so its owner can judge relevance in one glance. "
    "The input may include fetched page content (title, description, article text) from the "
    "linked URL, plus tweet context. Use web search at most once to verify current state. "
    "Be concise and factual. Return exactly three lines, no preamble:\n"
    "SUMMARY: <1-2 sentences: what this is and why it mattered>\n"
    "SIGNAL: <one short clause on whether it's still worth opening — e.g. "
    "'still the canonical reference', 'superseded by X', 'author shipped v2 since', "
    "'thread deleted, archived only'>\n"
    "STATUS: <current|dated|stale>"
)


def _parse_line(text: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+)$", text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _coerce_status(raw: str | None) -> RelevanceStatus:
    if raw:
        token = raw.strip().lower().split()[0].strip(".,:")
        if token in _VALID_STATUS:
            return token  # type: ignore[return-value]
    return "unknown"


def _too_many_tool_calls(exc: BaseException) -> bool:
    return "too many tool calls" in str(exc).lower()


def _research_bookmark_once(
    raw_text: str,
    url: str,
    *,
    skip_google_search: bool,
) -> BookmarkResearch:
    """Single Gemini call for bookmark research."""
    max_chars = settings.enrich_max_input_chars
    model = settings.gemini_flash_lite_model if skip_google_search else settings.gemini_model
    req: dict = {
        "model": model,
        "input": (
            "Research this saved bookmark. Prefer the fetched page content when present.\n\n"
            f"URL: {url}\n\n"
            f"Context:\n{raw_text[:max_chars]}"
        ),
        "system_instruction": _SYSTEM,
        "store": False,
    }
    if not skip_google_search:
        req["tools"] = [{"type": "google_search"}]
    interaction = create_interaction(
        label="bookmark-research-fast" if skip_google_search else "bookmark-research",
        **req,
    )
    grounded = parse_grounded_interaction(interaction)
    text = (grounded.text or interaction.output_text or "").strip()

    summary = _parse_line(text, "SUMMARY")
    signal = _parse_line(text, "SIGNAL")
    status = _coerce_status(_parse_line(text, "STATUS"))

    if not summary or is_bare_url(summary):
        if text and not is_bare_url(text):
            summary = text[:300]
        elif raw_text and not is_bare_url(raw_text):
            summary = raw_text[:200].strip()
        else:
            summary = "Link bookmark — web preview unavailable; open to inspect."
    if not signal:
        signal = "No additional web context found."

    return BookmarkResearch(
        research_summary=summary,
        relevance_signal=signal,
        relevance_status=status,
        research_sources=grounded.citations[:5],
    )


def research_bookmark(
    raw_text: str,
    url: str,
    *,
    skip_google_search: bool = False,
) -> BookmarkResearch:
    """Grounded research → summary, validation signal, status, and sources."""
    try:
        return _research_bookmark_once(raw_text, url, skip_google_search=skip_google_search)
    except Exception as exc:
        if skip_google_search or not _too_many_tool_calls(exc):
            raise
        logger.warning(
            "Gemini google_search overflow — retrying without search for %s",
            url[:80],
        )
        return _research_bookmark_once(raw_text, url, skip_google_search=True)
