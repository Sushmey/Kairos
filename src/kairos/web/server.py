"""Uvicorn entrypoint for kairos serve."""

from __future__ import annotations

import uvicorn

from kairos.config import settings


def run_server(*, host: str | None = None, port: int | None = None) -> None:
    host = host or "127.0.0.1"
    port = port or int(settings.web_base_url.rsplit(":", 1)[-1].rstrip("/") or 8420)
    uvicorn.run(
        "kairos.web.app:app",
        host=host,
        port=port,
        reload=False,
    )
