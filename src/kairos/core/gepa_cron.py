"""GEPA scheduled / nightly entrypoint."""

from __future__ import annotations

from kairos.core.eval_harness import feedback_readiness
from kairos.core.optimize import run_gepa
from kairos.models.optimize import GepaRunResult


async def run_gepa_nightly(*, days: int = 14, dry_run: bool = False) -> GepaRunResult:
    """Run GEPA only when enough feedback exists; safe for cron / Cloud Run."""
    readiness = await feedback_readiness(days=days)
    if not readiness.gepa_ready:
        return GepaRunResult(
            status="skipped",
            reason=f"only {readiness.feedback_count} feedback events (need ≥ {readiness.min_samples})",
            readiness=readiness,
        )
    return await run_gepa(days=days, dry_run=dry_run)
