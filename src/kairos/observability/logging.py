"""Loguru-based structured logging for Kairos."""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

from kairos.config import settings

_CONFIGURED = False

# Pipeline event kinds mirrored from the admin SSE feed.
_PIPELINE_LOG_KINDS = frozenset(
    {
        "session",
        "context",
        "pipeline",
        "intelligence",
        "activity",
        "indicator",
        "notification",
        "feedback",
    }
)


class InterceptHandler(logging.Handler):
    """Route stdlib logging (uvicorn, etc.) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        component = record.name
        if component.startswith("uvicorn."):
            component = "uvicorn"
        elif component == "fastapi":
            component = "http"

        logger.bind(component=component).opt(depth=depth, exception=record.exc_info).log(
            level,
            record.getMessage(),
        )


def _structured_extras(record: dict[str, Any]) -> str:
    skip = {"component", "structured"}
    parts: list[str] = []
    for key in sorted(record["extra"]):
        if key in skip:
            continue
        value = record["extra"][key]
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            text = str(value)
            if len(text) > 120:
                text = text[:117] + "…"
            parts.append(f"{key}={text}")
        else:
            parts.append(f"{key}={value}")
    return (" | " + " ".join(parts)) if parts else ""


def _patch_record(record: dict[str, Any]) -> None:
    record["extra"]["structured"] = _structured_extras(record)


def setup_logging(*, force: bool = False) -> None:
    """Configure loguru once for CLI, web server, and MCP."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    level = settings.log_level.upper()
    logger.remove()
    logger.configure(patcher=_patch_record, extra={"component": "app"})

    if settings.log_json:
        logger.add(
            sys.stderr,
            level=level,
            serialize=True,
        )
    else:
        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[component]: <10}</cyan> | "
            "{message}{extra[structured]}"
        )
        logger.add(
            sys.stderr,
            level=level,
            format=fmt,
            colorize=True,
            backtrace=settings.log_backtrace,
            diagnose=settings.log_diagnose,
        )

    intercept = InterceptHandler()
    logging.basicConfig(handlers=[intercept], level=0, force=True)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "asyncio"):
        std = logging.getLogger(name)
        std.handlers = [intercept]
        std.propagate = False

    # Uvicorn access lines are replaced by our FastAPI middleware when log_access is on.
    if not settings.log_access:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(component: str = "app"):
    """Return a loguru logger bound to a logical component."""
    return logger.bind(component=component)


def get_uvicorn_log_config() -> dict[str, Any]:
    """Uvicorn log config that forwards to loguru via InterceptHandler."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "intercept": {
                "()": "kairos.observability.logging.InterceptHandler",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["intercept"], "level": "INFO", "propagate": False},
            "uvicorn.error": {"handlers": ["intercept"], "level": "INFO", "propagate": False},
            "uvicorn.access": {
                "handlers": ["intercept"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }


def _sanitize_log_data(data: dict[str, Any]) -> dict[str, Any]:
    """Keep structured logs readable — omit large payloads."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key == "context" and isinstance(value, dict):
            out[key] = {
                "location_type": value.get("location_type"),
                "calendar_gap_minutes": value.get("calendar_gap_minutes"),
                "surfaces_today": value.get("surfaces_today"),
            }
        elif key == "digest" and isinstance(value, dict):
            out[key] = {
                "cluster_name": value.get("cluster_name"),
                "links": len(value.get("links") or []),
            }
        elif key == "delivery" and isinstance(value, dict):
            out[key] = {"dashboard_url": value.get("dashboard_url")}
        else:
            out[key] = value
    return out


def log_pipeline_event(*, kind: str, message: str, **data: Any) -> None:
    """Mirror SSE pipeline events to server logs with structured fields."""
    if not settings.log_pipeline_events:
        return
    if kind not in _PIPELINE_LOG_KINDS:
        return

    safe = _sanitize_log_data(data)
    log = get_logger("pipeline").bind(event_kind=kind, **safe)
    if kind == "feedback":
        log.warning(message)
    else:
        log.info(message)
