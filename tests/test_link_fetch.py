"""Tests for link fetch and URL helpers."""

from kairos.bookmarks.link_fetch import _extract_preview, pick_fetch_url
from kairos.bookmarks.urls import build_bookmark_link_card, compose_research_input, is_bare_url


def test_is_bare_url():
    assert is_bare_url("https://t.co/abc123")
    assert is_bare_url("")
    assert not is_bare_url("Great thread on fan-out architecture")


def test_extract_preview_from_html():
    html = """
    <html><head>
    <title>Fallback title</title>
    <meta property="og:title" content="Article headline" />
    <meta property="og:description" content="A detailed explainer on sharding." />
    </head><body><p>Body paragraph about databases.</p></body></html>
    """
    title, desc, body = _extract_preview(html, max_body=500)
    assert title == "Article headline"
    assert desc == "A detailed explainer on sharding."
    assert "Body paragraph" in (body or "")


def test_pick_fetch_url_follows_shortlinks():
    doc = {"url": "https://t.co/abc123"}
    assert pick_fetch_url(doc) == "https://t.co/abc123"


def test_card_uses_fetched_link_content():
    doc = {
        "x_tweet_id": "99",
        "url": "https://t.co/abc",
        "raw_text": "https://t.co/abc",
        "author_username": "aparnadhinak",
        "topic_tags": ["news"],
        "link_final_url": "https://example.com/post",
        "link_title": "How we shard activity feeds",
        "link_description": "Engineering deep dive on fan-out vs fan-in.",
        "link_body_excerpt": "We compared push and pull models across three production deployments.",
    }
    card = build_bookmark_link_card(doc)
    assert card is not None
    assert card.title == "How we shard activity feeds"
    assert card.summary and "fan-out" in card.summary
    assert card.summary and "t.co" not in card.summary


def test_compose_research_includes_fetched_page():
    doc = {
        "url": "https://t.co/x",
        "raw_text": "https://t.co/x",
        "link_final_url": "https://example.com/a",
        "link_title": "Headline",
        "link_body_excerpt": "Article body text.",
    }
    text = compose_research_input(doc)
    assert "Fetched page" in text
    assert "Headline" in text
    assert "Article body text" in text
