"""Ranking pipeline + interrupt gate (policy core)."""

from __future__ import annotations

import asyncio
import logging

import numpy as np

from kairos.config import settings
from kairos.core.bandit import thompson_sample
from kairos.core.moment import context_class, moment_text
from kairos.db.bandit import ensure_bandit_indexes, get_bandit_params
from kairos.db.bookmarks import list_bookmarks_by_cluster
from kairos.db.clusters import list_clusters
from kairos.db.feedback import list_snoozed_cluster_ids
from kairos.db.mongo import close_mongo
from kairos.embeddings.encoder import encode_query
from kairos.llm.generation import generate_cluster_digest
from kairos.models.schemas import ClusterDigest, ContextSnapshot, SurfaceDecision
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _gate_reasons(
    context: ContextSnapshot,
    *,
    adjusted_score: float | None,
) -> dict[str, bool]:
    threshold = settings.surface_score_threshold
    return {
        "daily_budget": context.surfaces_today < settings.daily_surface_budget,
        "calendar_gap": context.calendar_gap_minutes >= settings.min_calendar_gap_minutes,
        "min_gap": (
            context.time_since_last_surface_minutes
            >= settings.min_gap_between_surfaces_minutes
        ),
        "score_threshold": adjusted_score is not None and adjusted_score >= threshold,
    }


def _should_surface(gate_reasons: dict[str, bool]) -> bool:
    return all(gate_reasons.values())


def _bookmark_snippets(members: list[dict]) -> list[str]:
    return [(m.get("raw_text") or "").strip()[:300] for m in members if m.get("raw_text")]


def _merge_bookmark_links(digest: ClusterDigest, members: list[dict]) -> ClusterDigest:
    """Prefer real bookmark URLs over LLM placeholders."""
    links: list[dict[str, str]] = []
    for doc in members[:5]:
        url = doc.get("url") or ""
        if not url:
            continue
        label = (doc.get("raw_text") or url).replace("\n", " ")[:80]
        mode = doc.get("consumption_mode") or "skim"
        links.append({"url": url, "label": label, "consumption_mode": mode})
    if not links:
        return digest
    return digest.model_copy(update={"links": links})


async def evaluate_surface(
    context: ContextSnapshot,
    context_override: str | None = None,
) -> SurfaceDecision:
    """Run feasibility → vector match → bandit → interrupt gate → digest."""
    if context_override:
        event_bus.emit("context_override", context_override)

    try:
        await ensure_bandit_indexes()
        clusters = await list_clusters()
        clusters = [c for c in clusters if c.get("centroid_embedding")]
        ctx_class = context_class(context)
        snoozed_ids = set(await list_snoozed_cluster_ids(ctx_class))
        if snoozed_ids:
            clusters = [c for c in clusters if c.get("cluster_id") not in snoozed_ids]

        best_vector = 0.0
        best_adjusted = 0.0
        best_cluster: dict | None = None
        digest: ClusterDigest | None = None

        if clusters:
            query = moment_text(context, context_override)
            moment_vector = await asyncio.to_thread(encode_query, query)

            for cluster in clusters:
                centroid = cluster.get("centroid_embedding")
                if not centroid:
                    continue
                vector_score = _cosine(moment_vector, centroid)
                params = await get_bandit_params(cluster["cluster_id"], ctx_class)
                bandit_weight = thompson_sample(params["alpha"], params["beta"])
                adjusted = vector_score * bandit_weight

                if adjusted > best_adjusted:
                    best_adjusted = adjusted
                    best_vector = vector_score
                    best_cluster = cluster

            logger.info(
                "Ranked %s clusters; best=%s vector=%.3f adjusted=%.3f",
                len(clusters),
                (best_cluster or {}).get("name"),
                best_vector,
                best_adjusted,
            )

        gate_reasons = _gate_reasons(context, adjusted_score=best_adjusted if best_cluster else None)
        should_surface = _should_surface(gate_reasons) and best_cluster is not None

        if should_surface and best_cluster:
            members = await list_bookmarks_by_cluster(best_cluster["cluster_id"], limit=8)
            snippets = _bookmark_snippets(members)
            digest = await asyncio.to_thread(
                generate_cluster_digest,
                best_cluster["cluster_id"],
                best_cluster.get("name") or "Cluster",
                best_cluster.get("summary") or "",
                snippets,
                context,
                member_count=best_cluster.get("member_count") or len(members),
            )
            digest = _merge_bookmark_links(digest, members)
            digest = digest.model_copy(update={"cluster_id": best_cluster["cluster_id"]})

        decision = SurfaceDecision(
            should_surface=should_surface,
            cluster_id=best_cluster["cluster_id"] if should_surface and best_cluster else None,
            digest=digest,
            gate_reasons=gate_reasons,
            adjusted_score=best_adjusted if best_cluster else None,
            context=context,
        )
    except RuntimeError as exc:
        logger.warning("Ranking skipped: %s", exc)
        gate_reasons = _gate_reasons(context, adjusted_score=None)
        gate_reasons["score_threshold"] = False
        decision = SurfaceDecision(
            should_surface=False,
            gate_reasons=gate_reasons,
            context=context,
        )
    finally:
        await close_mongo()

    event_bus.emit(
        "activity",
        "Ranking pipeline complete",
        should_surface=decision.should_surface,
        gate_reasons=decision.gate_reasons,
        cluster_id=decision.cluster_id,
        adjusted_score=decision.adjusted_score,
    )
    return decision
