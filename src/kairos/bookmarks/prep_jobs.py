"""Run bookmark prep jobs in the background."""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from kairos.bookmarks.pipeline import PipelineResult, run_bookmark_prep
from kairos.db.prep_jobs import update_prep_job
from kairos.models.jobs import PrepJobParams, PrepJobResult

logger = logging.getLogger(__name__)


async def execute_prep_job(job_id: str, params: PrepJobParams | dict[str, Any]) -> None:
    parsed = PrepJobParams.model_validate(params)
    await update_prep_job(job_id, status="running")
    try:
        result = await run_bookmark_prep(
            sync=parsed.sync,
            max_pages=parsed.max_pages,
            skip_enrich=parsed.skip_enrich,
            skip_research=parsed.skip_research,
            skip_embed=parsed.skip_embed,
            skip_cluster=parsed.skip_cluster,
            research_limit=parsed.research_limit,
            research_concurrency=parsed.research_concurrency,
            research_clustered_only=parsed.research_clustered_only(),
        )
        await update_prep_job(
            job_id,
            status="done",
            result=_serialize_prep_result(result),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Prep job %s failed", job_id)
        await update_prep_job(job_id, status="failed", error=str(exc))


def _serialize_prep_result(result: PipelineResult) -> PrepJobResult:
    payload: dict[str, Any] = {}
    if result.sync is not None:
        payload["sync"] = asdict(result.sync)
    payload["enrich"] = asdict(result.enrich)
    if result.research is not None:
        payload["research"] = asdict(result.research)
    payload["embed"] = asdict(result.embed)
    if result.cluster is not None:
        payload["cluster"] = asdict(result.cluster)
    payload["cluster_skipped"] = result.cluster_skipped
    payload["cluster_skip_reason"] = result.cluster_skip_reason
    return PrepJobResult.model_validate(payload)
