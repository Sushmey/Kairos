"""Central Gemini Interactions API calls with optional I/O tracing."""

from __future__ import annotations

import orjson
from pathlib import Path
from typing import Any

from loguru import logger

from kairos.config import settings
from kairos.llm.client import get_genai_client

_LOG = logger.bind(component="gemini")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _format_input(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return orjson.dumps(value, option=orjson.OPT_INDENT_2, default=str).decode()
    except TypeError:
        return str(value)


def _log_io(label: str, *, request: dict[str, Any], response_text: str) -> None:
    if not settings.gemini_log_io:
        return

    max_chars = settings.gemini_log_io_max_chars
    lines = [
        f"── Gemini [{label}] ──",
        f"model: {request.get('model', '?')}",
    ]
    if request.get("tools"):
        lines.append(f"tools: {request['tools']}")
    if request.get("system_instruction"):
        lines.append(
            "system:\n"
            + _truncate(_format_input(request["system_instruction"]), max_chars)
        )
    lines.append("input:\n" + _truncate(_format_input(request.get("input")), max_chars))
    lines.append("output:\n" + _truncate(response_text, max_chars))

    payload = "\n".join(lines)
    _LOG.info(payload)

    path = settings.gemini_log_io_path
    if path:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n\n")


def create_interaction(*, label: str, **kwargs: Any) -> Any:
    """Create a Gemini interaction; log request/response when GEMINI_LOG_IO=true."""
    client = get_genai_client()
    interaction = client.interactions.create(**kwargs)
    output = (interaction.output_text or "").strip()
    _log_io(label, request=kwargs, response_text=output)
    return interaction
