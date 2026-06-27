"""Apply enrichment metadata to bookmark documents during ingest."""

from __future__ import annotations

from kairos.llm.enrich_batch import EnrichmentJob, enrich_jobs_concurrent
from kairos.models.schemas import BookmarkDocument, BookmarkEnrichment


async def enrich_bookmark_documents(
    docs: list[BookmarkDocument],
    *,
    concurrency: int | None = None,
) -> tuple[list[BookmarkDocument], list[str], int]:
    """Enrich bookmark docs in parallel. Returns docs, errors, enriched count."""
    jobs = [
        EnrichmentJob(x_tweet_id=doc.x_tweet_id, raw_text=doc.raw_text, url=doc.url)
        for doc in docs
        if doc.raw_text
    ]
    if not jobs:
        return docs, [], 0

    outcomes = await enrich_jobs_concurrent(jobs, concurrency=concurrency)
    enrichment_by_id: dict[str, BookmarkEnrichment] = {}
    errors: list[str] = []

    for outcome in outcomes:
        if outcome.error:
            errors.append(f"{outcome.x_tweet_id}: {outcome.error}")
        elif outcome.enrichment is not None:
            enrichment_by_id[outcome.x_tweet_id] = outcome.enrichment

    enriched_docs: list[BookmarkDocument] = []
    for doc in docs:
        enrichment = enrichment_by_id.get(doc.x_tweet_id)
        if not enrichment:
            enriched_docs.append(doc)
            continue
        enriched_docs.append(
            doc.model_copy(
                update={
                    "topic_tags": enrichment.topic_tags,
                    "consumption_mode": enrichment.consumption_mode,
                    "energy_cost": enrichment.energy_cost,
                    "geo_anchor": enrichment.geo_anchor,
                    "perishability": enrichment.perishability,
                }
            )
        )

    return enriched_docs, errors, len(enrichment_by_id)
