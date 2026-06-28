"""Display URL helpers for bookmark links in digests."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from kairos.models.schemas import DigestLinkCard, DigestSourceLink

_SHORTLINK_HOSTS = frozenset(
    {
        "x.com",
        "twitter.com",
        "t.co",
        "mobile.twitter.com",
    }
)
_REDIRECT_HOSTS = frozenset(
    {
        "vertexaisearch.cloud.google.com",
    }
)
_EXCERPT_MAX = 280
_TITLE_MAX = 90
_URL_IN_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def is_internal_or_redirect(url: str) -> bool:
    host = _host(url)
    return host in _SHORTLINK_HOSTS or host in _REDIRECT_HOSTS


def is_bare_url(text: str) -> bool:
    """True when text is empty or only URL(s) — not useful as card copy."""
    cleaned = text.replace("\n", " ").strip()
    if not cleaned:
        return True
    without_urls = _URL_IN_TEXT.sub("", cleaned).strip(" \t.,;:-—")
    return not without_urls


def pick_display_url(
    stored_url: str,
    sources: list[dict] | None = None,
    *,
    x_tweet_id: str | None = None,
    link_final_url: str | None = None,
) -> str:
    """Prefer a canonical external URL when the bookmark stored an X wrapper."""
    if link_final_url and not is_internal_or_redirect(link_final_url):
        return link_final_url
    if stored_url and not is_internal_or_redirect(stored_url):
        return stored_url
    for source in sources or []:
        candidate = (source.get("url") or "").strip()
        if candidate and not is_internal_or_redirect(candidate):
            return candidate
    if x_tweet_id and is_internal_or_redirect(stored_url):
        return f"https://x.com/i/web/status/{x_tweet_id}"
    return stored_url


def _clean_text(text: str) -> str:
    return text.replace("\n", " ").strip()


def _truncate(text: str, limit: int) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _humanize_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    readable = [t.replace("-", " ").replace("_", " ") for t in tags[:5]]
    if len(readable) == 1:
        return readable[0]
    if len(readable) == 2:
        return f"{readable[0]} and {readable[1]}"
    return ", ".join(readable[:-1]) + f", and {readable[-1]}"


def _author_handle(doc: dict) -> str:
    username = (doc.get("author_username") or "").strip()
    if not username:
        return ""
    return username if username.startswith("@") else f"@{username}"


def _context_annotation_text(doc: dict) -> str:
    parts: list[str] = []
    for ann in doc.get("context_annotations") or []:
        entity = ann.get("entity") or {}
        name = (entity.get("name") or "").strip()
        desc = (entity.get("description") or "").strip()
        if name and desc and not is_bare_url(desc):
            parts.append(f"{name}: {desc}")
        elif name:
            parts.append(name)
    return _truncate(" · ".join(parts), _EXCERPT_MAX)


def pick_usable_text(doc: dict) -> str:
    """Best available human text — fetched article, then tweet body."""
    from kairos.bookmarks.link_fetch import link_content_text

    link_text = link_content_text(doc)
    if link_text and not is_bare_url(link_text):
        return link_text

    raw = _clean_text(doc.get("raw_text") or "")
    if raw and not is_bare_url(raw):
        return raw

    for ref in doc.get("referenced_tweets") or []:
        ref_text = _clean_text(ref.get("text") or "")
        if ref_text and not is_bare_url(ref_text):
            return ref_text

    annotation = _context_annotation_text(doc)
    if annotation:
        return annotation

    return ""


def compose_research_input(doc: dict) -> str:
    """Rich context for grounded research — tweet + fetched link page."""
    from kairos.bookmarks.link_fetch import link_content_text

    parts: list[str] = []
    link_text = link_content_text(doc)
    if link_text:
        final = (doc.get("link_final_url") or doc.get("url") or "").strip()
        header = f"Fetched page ({final}):" if final else "Fetched page:"
        parts.append(f"{header}\n{link_text[:8000]}")

    raw = _clean_text(doc.get("raw_text") or "")
    if raw and not is_bare_url(raw):
        parts.append(f"Tweet text:\n{raw}")

    for ref in doc.get("referenced_tweets") or []:
        ref_type = ref.get("type") or "reference"
        ref_text = _clean_text(ref.get("text") or "")
        if ref_text:
            parts.append(f"{ref_type}: {ref_text[:400]}")

    author = _author_handle(doc)
    if author:
        parts.append(f"Shared by {author}")

    tags = doc.get("topic_tags") or []
    if tags:
        parts.append(f"Topics: {', '.join(tags)}")

    url = doc.get("url") or ""
    if url:
        parts.append(f"Link: {url}")

    return "\n".join(parts) if parts else url


def _source_title(sources: list[dict]) -> str:
    for source in sources:
        title = (source.get("title") or "").strip()
        if title and not is_bare_url(title):
            return _truncate(title, _TITLE_MAX)
    return ""


def _link_only_title(doc: dict) -> str:
    author = _author_handle(doc)
    tags = doc.get("topic_tags") or []
    if tags:
        topic = _humanize_tags(tags[:3]).title()
        if author:
            return f"{topic} — {author}"
        return topic
    if author:
        return f"Link shared by {author}"
    return "Saved link"


def _link_only_summary(doc: dict) -> str:
    author = _author_handle(doc)
    tags = doc.get("topic_tags") or []
    topic_line = _humanize_tags(tags)
    parts: list[str] = []
    if topic_line:
        parts.append(f"Bookmark about {topic_line}.")
    elif author:
        parts.append(f"Link bookmarked from {author}.")
    else:
        parts.append("Bookmarked link with no preview text.")
    perish = doc.get("perishability")
    if perish == "time-sensitive":
        parts.append("Marked time-sensitive — verify before opening.")
    elif perish == "evergreen":
        parts.append("Marked evergreen reference material.")
    if not doc.get("research_summary"):
        parts.append("Web preview not fetched yet.")
    return " ".join(parts)


def bookmark_snippet_text(doc: dict) -> str:
    """One-line snippet for digest generation — skips bare URL-only tweets."""
    usable = pick_usable_text(doc)
    if usable:
        return usable[:300]
    author = _author_handle(doc)
    tags = doc.get("topic_tags") or []
    parts: list[str] = []
    if author:
        parts.append(f"Link from {author}")
    if tags:
        parts.append(_humanize_tags(tags))
    return " — ".join(parts) if parts else (doc.get("url") or "")[:80]


def pick_link_title(
    doc: dict,
    *,
    fallback_url: str,
    sources: list[dict] | None = None,
) -> str:
    """Short card title — never a bare t.co / x.com URL."""
    link_title = _clean_text(doc.get("link_title") or "")
    if link_title and not is_bare_url(link_title):
        return _truncate(link_title, _TITLE_MAX)

    research = _clean_text(doc.get("research_summary") or "")
    if research and not is_bare_url(research):
        first = research.split(".")[0].strip()
        if 12 <= len(first) <= _TITLE_MAX:
            return first
        if len(research) <= _TITLE_MAX:
            return research
        return _truncate(research, _TITLE_MAX)

    source_title = _source_title(sources or [])
    if source_title:
        return source_title

    usable = pick_usable_text(doc)
    if usable:
        return _truncate(usable, _TITLE_MAX)

    raw = _clean_text(doc.get("raw_text") or "")
    if raw and not is_bare_url(raw):
        return _truncate(raw, _TITLE_MAX)

    return _link_only_title(doc)


def pick_link_excerpt(doc: dict) -> str:
    """Original saved text for cards when research is absent or supplemental."""
    usable = pick_usable_text(doc)
    if usable:
        return _truncate(usable, _EXCERPT_MAX)
    raw = _clean_text(doc.get("raw_text") or "")
    if raw and not is_bare_url(raw):
        return _truncate(raw, _EXCERPT_MAX)
    return ""


def pick_link_summary(
    doc: dict,
    *,
    sources: list[dict] | None = None,
) -> str:
    """What the user reads to judge value without opening the link."""
    research = _clean_text(doc.get("research_summary") or "")
    if research and not is_bare_url(research):
        return research

    desc = _clean_text(doc.get("link_description") or "")
    body = _clean_text(doc.get("link_body_excerpt") or "")
    if desc or body:
        parts = [p for p in (desc, body) if p and not is_bare_url(p)]
        if parts:
            combined = "\n\n".join(parts)
            return _truncate(combined, _EXCERPT_MAX * 2)

    signal = _clean_text(doc.get("relevance_signal") or "")
    if signal and signal != "No additional web context found." and not is_bare_url(signal):
        usable = pick_usable_text(doc)
        if usable:
            return f"{usable} — {signal}"
        return signal

    excerpt = pick_link_excerpt(doc)
    if excerpt:
        return excerpt

    return _link_only_summary(doc)


def pick_link_label(
    doc: dict,
    *,
    fallback_url: str,
    sources: list[dict] | None = None,
) -> str:
    """Human-readable link title for digest cards (alias of pick_link_title)."""
    return pick_link_title(doc, fallback_url=fallback_url, sources=sources)


def build_bookmark_link_card(doc: dict) -> DigestLinkCard | None:
    """Rich link payload for digest cards — title, summary, tags, validation."""
    stored_url = doc.get("url") or ""
    if not stored_url:
        return None

    raw_sources = doc.get("research_sources") or []
    sources = [
        DigestSourceLink(url=s["url"], title=s.get("title"))
        for s in raw_sources
        if s.get("url") and not is_internal_or_redirect(s["url"])
    ]
    display_url = pick_display_url(
        stored_url,
        [{"url": s.url, "title": s.title} for s in sources],
        x_tweet_id=doc.get("x_tweet_id"),
        link_final_url=doc.get("link_final_url"),
    )
    title = pick_link_title(
        doc,
        fallback_url=display_url or stored_url,
        sources=[{"url": s.url, "title": s.title} for s in sources],
    )
    research = _clean_text(doc.get("research_summary") or "")
    excerpt = pick_link_excerpt(doc)
    summary = pick_link_summary(doc, sources=[{"url": s.url, "title": s.title} for s in sources])

    card_kwargs: dict = {
        "url": display_url,
        "label": title,
        "title": title,
        "consumption_mode": doc.get("consumption_mode") or "skim",
    }
    if summary:
        card_kwargs["summary"] = summary
    if excerpt and excerpt != summary:
        card_kwargs["excerpt"] = excerpt
    author = _author_handle(doc)
    if author:
        card_kwargs["author"] = author
    tags = doc.get("topic_tags") or []
    if tags:
        card_kwargs["tags"] = tags[:6]
    if doc.get("relevance_signal"):
        card_kwargs["signal"] = doc["relevance_signal"]
    if doc.get("relevance_status"):
        card_kwargs["status"] = doc["relevance_status"]
    elif doc.get("perishability"):
        card_kwargs["status"] = {
            "evergreen": "current",
            "dated": "dated",
            "time-sensitive": "stale",
        }.get(doc["perishability"], "unknown")
    if doc.get("perishability"):
        card_kwargs["perishability"] = doc["perishability"]
    if doc.get("energy_cost") is not None:
        card_kwargs["energy_cost"] = doc["energy_cost"]
    if sources:
        card_kwargs["sources"] = sources
    if research and not is_bare_url(research):
        card_kwargs["researched"] = True
    elif doc.get("link_body_excerpt") or doc.get("link_title"):
        card_kwargs["researched"] = False
        card_kwargs["link_fetched"] = True
    elif not research:
        card_kwargs["pending_research"] = True
    return DigestLinkCard(**card_kwargs)
