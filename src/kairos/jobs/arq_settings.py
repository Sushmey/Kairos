"""Arq worker settings — async prep jobs on Redis."""

from __future__ import annotations

from typing import Any

from arq.connections import RedisSettings

from kairos.config import settings


async def execute_prep_job(ctx: dict[str, Any], job_id: str, params: dict[str, Any]) -> None:
    """Arq task: run full bookmark prep pipeline."""
    _ = ctx
    from kairos.bookmarks.prep_jobs import execute_prep_job as run_prep_job

    await run_prep_job(job_id, params)


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


class WorkerSettings:
    """Entrypoint for: uv run arq kairos.jobs.arq_settings.WorkerSettings"""

    functions = [execute_prep_job]
    redis_settings = get_redis_settings()
    job_timeout = 3600
    max_tries = 1
