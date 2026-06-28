"""Uvicorn entrypoint for kairos serve."""

from __future__ import annotations

import uvicorn

from kairos.config import settings
from kairos.observability.logging import get_logger, get_uvicorn_log_config, setup_logging

log = get_logger("server")


def run_server(*, host: str | None = None, port: int | None = None) -> None:
    setup_logging()
    host = host or "127.0.0.1"
    port = port or int(settings.web_base_url.rsplit(":", 1)[-1].rstrip("/") or 8420)
    log.info("Starting Kairos web server on http://{}:{}", host, port)
    uvicorn.run(
        "kairos.web.app:app",
        host=host,
        port=port,
        reload=False,
        log_config=get_uvicorn_log_config(),
        access_log=False,
    )
