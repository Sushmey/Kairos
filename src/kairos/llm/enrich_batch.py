"""Concurrent bookmark enrichment helpers."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from kairos.config import settings
from kairos.llm.generation import enrich_bookmark
from kairos.models.schemas import BookmarkEnrichment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnrichmentJob:
    x_tweet_id: str
    raw_text: str
    url: str


@dataclass
class EnrichmentOutcome:
    x_tweet_id: str
    enrichment: BookmarkEnrichment | None = None
    error: str | None = None


async def enrich_jobs_concurrent(
    jobs: list[EnrichmentJob],
    *,
    concurrency: int | None = None,
) -> list[EnrichmentOutcome]:
    """Run bookmark enrichment in parallel via thread pool (sync Gemini SDK)."""
    if not jobs:
        return []

    limit = concurrency if concurrency is not None else settings.enrich_concurrency
    limit = max(1, min(limit, 32))
    semaphore = asyncio.Semaphore(limit)

    async def _run(job: EnrichmentJob) -> EnrichmentOutcome:
        async with semaphore:
            try:
                enrichment = await asyncio.to_thread(
                    enrich_bookmark, job.raw_text, job.url
                )
                return EnrichmentOutcome(x_tweet_id=job.x_tweet_id, enrichment=enrichment)
            except Exception as exc:  # noqa: BLE001 — per-job failure, continue batch
                logger.exception("Enrichment failed for %s", job.x_tweet_id)
                return EnrichmentOutcome(x_tweet_id=job.x_tweet_id, error=str(exc))

    return list(await asyncio.gather(*(_run(job) for job in jobs)))
