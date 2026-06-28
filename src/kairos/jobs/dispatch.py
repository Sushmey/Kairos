"""Dispatch background jobs to local FastAPI tasks or Arq (Redis)."""

from __future__ import annotations

from typing import Any

from fastapi import BackgroundTasks

from kairos.config import settings


async def dispatch_prep_job(
    job_id: str,
    params: dict[str, Any],
    *,
    background_tasks: BackgroundTasks | None = None,
) -> str:
    """Enqueue prep work. Returns backend used: local | arq."""
    backend = (settings.job_backend or "local").lower()

    if backend == "arq":
        try:
            from arq import create_pool
        except ImportError as exc:
            raise RuntimeError("Install queue extras: uv sync --extra queue") from exc

        from kairos.jobs.arq_settings import get_redis_settings

        pool = await create_pool(get_redis_settings())
        try:
            await pool.enqueue_job("execute_prep_job", job_id, params)
        finally:
            await pool.aclose()
        return "arq"

    if background_tasks is None:
        raise ValueError("background_tasks required when JOB_BACKEND=local")

    from kairos.bookmarks.prep_jobs import execute_prep_job

    background_tasks.add_task(execute_prep_job, job_id, params)
    return "local"
