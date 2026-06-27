"""Incremental bookmark pipeline — sync, enrich, embed, cluster."""

from __future__ import annotations

from dataclasses import dataclass

from kairos.bookmarks.enrich import EnrichResult, enrich_stored_bookmarks
from kairos.bookmarks.index import ClusterResult, EmbedResult, cluster_stored_bookmarks, embed_stored_bookmarks
from kairos.db.bookmarks import count_unclustered_embedded
from kairos.ingest.sync import SyncResult, sync_bookmarks_from_x


@dataclass
class PipelineResult:
    sync: SyncResult
    enrich: EnrichResult
    embed: EmbedResult
    cluster: ClusterResult | None = None
    cluster_skipped: bool = False
    cluster_skip_reason: str | None = None


async def run_incremental_pipeline(
    *,
    incremental_sync: bool = True,
    max_pages: int | None = None,
    skip_enrich: bool = False,
    skip_embed: bool = False,
    skip_cluster: bool = False,
    recluster_if_stale: bool = True,
    enrich_concurrency: int | None = None,
) -> PipelineResult:
    """Fetch new/changed bookmarks from X, then process only stale rows in MongoDB."""
    sync = await sync_bookmarks_from_x(
        max_pages=max_pages,
        incremental=incremental_sync,
        enrich=not skip_enrich,
        enrich_concurrency=enrich_concurrency,
    )

    enrich = EnrichResult()
    if not skip_enrich:
        enrich = await enrich_stored_bookmarks(concurrency=enrich_concurrency)

    embed = EmbedResult()
    if not skip_embed:
        embed = await embed_stored_bookmarks()

    cluster: ClusterResult | None = None
    cluster_skipped = False
    cluster_skip_reason: str | None = None

    if skip_cluster:
        cluster_skipped = True
        cluster_skip_reason = "skip_cluster flag"
    elif recluster_if_stale:
        unclustered = await count_unclustered_embedded()
        new_vectors = embed.embedded > 0
        if unclustered > 0 or new_vectors:
            cluster = await cluster_stored_bookmarks()
        else:
            cluster_skipped = True
            cluster_skip_reason = "no new embeddings or unclustered bookmarks"
    else:
        cluster = await cluster_stored_bookmarks()

    return PipelineResult(
        sync=sync,
        enrich=enrich,
        embed=embed,
        cluster=cluster,
        cluster_skipped=cluster_skipped,
        cluster_skip_reason=cluster_skip_reason,
    )
