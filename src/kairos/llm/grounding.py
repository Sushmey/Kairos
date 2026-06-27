"""Extract citations from Gemini Interactions API grounding responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kairos.models.schemas import UrlCitation


@dataclass
class GroundedText:
    text: str
    citations: list[UrlCitation]


def parse_grounded_interaction(interaction: Any) -> GroundedText:
    """Parse model_output text and url_citation annotations from an interaction."""
    text_parts: list[str] = []
    citations: list[UrlCitation] = []
    seen_urls: set[str] = set()

    for step in interaction.steps or []:
        if getattr(step, "type", None) != "model_output":
            continue
        for block in step.content or []:
            if getattr(block, "type", None) != "text":
                continue
            body = getattr(block, "text", None) or ""
            if body:
                text_parts.append(body.strip())
            for annotation in getattr(block, "annotations", None) or []:
                if getattr(annotation, "type", None) != "url_citation":
                    continue
                url = getattr(annotation, "url", None) or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                start = getattr(annotation, "start_index", None)
                end = getattr(annotation, "end_index", None)
                cited_text = None
                if isinstance(start, int) and isinstance(end, int) and body:
                    cited_text = body[start:end].strip() or None
                citations.append(
                    UrlCitation(
                        url=url,
                        title=getattr(annotation, "title", None),
                        cited_text=cited_text,
                    )
                )

    return GroundedText(text="\n\n".join(part for part in text_parts if part), citations=citations)
