"""Fixed fixtures for offline GEPA / digest prompt evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from kairos.models.optimize import FixtureEvalCase, FixtureEvalResult, GepaReadiness
from kairos.models.schemas import ClusterDigest, ContextSnapshot


@dataclass(frozen=True)
class DigestEvalFixture:
    """Context × cluster pair with expected digest quality signals."""

    name: str
    context: ContextSnapshot
    cluster_name: str
    cluster_summary: str
    snippets: list[str]
    expect_why_now: bool = True
    expect_summary: bool = True


FIXTURES: list[DigestEvalFixture] = [
    DigestEvalFixture(
        name="pre_meeting_infra",
        context=ContextSnapshot(
            calendar_gap_minutes=90,
            upcoming_event_title="Architecture review",
            topical_affinity="work",
            attention_capacity="high",
            moment_narrative="90 minutes before an architecture review — deep technical reading fits.",
        ),
        cluster_name="Distributed systems",
        cluster_summary="CAP, sharding, and stream processing bookmarks.",
        snippets=[
            "Thread on fan-out vs fan-in for activity feeds",
            "Jepsen results for a Postgres variant",
        ],
    ),
    DigestEvalFixture(
        name="tight_calendar",
        context=ContextSnapshot(
            calendar_gap_minutes=8,
            upcoming_event_title="Standup",
            topical_affinity="work",
            attention_capacity="low",
            moment_narrative="Eight minutes between meetings — only skim-level content fits.",
        ),
        cluster_name="Product management",
        cluster_summary="PM essays and roadmap threads.",
        snippets=["Short thread on prioritization frameworks"],
        expect_why_now=True,
    ),
    DigestEvalFixture(
        name="evening_personal",
        context=ContextSnapshot(
            calendar_gap_minutes=120,
            topical_affinity="explore",
            attention_capacity="medium",
            moment_narrative="Long evening gap — room for longer reads or creative topics.",
        ),
        cluster_name="Creative writing",
        cluster_summary="Essays on narrative craft and reading lists.",
        snippets=["On showing vs telling in fiction"],
    ),
]


async def feedback_readiness(*, days: int = 14, min_samples: int | None = None) -> GepaReadiness:
    """Report whether enough live feedback exists to run GEPA."""
    from kairos.config import settings
    from kairos.core.optimize import _load_feedback_sample

    required = min_samples if min_samples is not None else settings.gepa_min_samples
    events = await _load_feedback_sample(days=days)
    positive = sum(1 for e in events if (e.get("derived_reward") or 0) > 0)
    negative = len(events) - positive
    return GepaReadiness(
        feedback_count=len(events),
        positive_count=positive,
        negative_count=negative,
        min_samples=required,
        gepa_ready=len(events) >= required,
        days_window=days,
    )


def score_digest_structural(digest: ClusterDigest) -> dict[str, bool]:
    """Cheap offline checks — no LLM judge."""
    summary_ok = bool(digest.summary and len(digest.summary.strip()) > 20)
    why_ok = bool(digest.why_now and len(digest.why_now.strip()) > 15)
    links_ok = bool(digest.links)
    return {
        "has_summary": summary_ok,
        "has_why_now": why_ok,
        "has_links": links_ok,
    }


async def run_fixture_eval(*, prompt_override: str | None = None) -> FixtureEvalResult:
    """Generate digests for fixed fixtures using runtime-fast mode (one call each)."""
    from kairos.config import settings
    from kairos.llm.generation import generate_cluster_digest

    if not settings.gemini_api_key:
        return FixtureEvalResult(status="skipped", reason="GEMINI_API_KEY not set")

    results: list[FixtureEvalCase] = []
    passed = 0
    for fx in FIXTURES:
        digest = generate_cluster_digest(
            cluster_id=f"eval-{fx.name}",
            cluster_name=fx.cluster_name,
            cluster_summary=fx.cluster_summary,
            bookmark_snippets=fx.snippets,
            context=fx.context,
            member_count=len(fx.snippets),
            prompt_override=prompt_override,
        )
        checks = score_digest_structural(digest)
        ok = (
            (not fx.expect_summary or checks["has_summary"])
            and (not fx.expect_why_now or checks["has_why_now"])
        )
        passed += int(ok)
        results.append(
            FixtureEvalCase(fixture=fx.name, passed=ok, **checks)
        )

    return FixtureEvalResult(
        status="ok",
        fixtures=len(FIXTURES),
        passed=passed,
        pass_rate=round(passed / len(FIXTURES), 3) if FIXTURES else 0.0,
        results=results,
        prompt_override=prompt_override is not None,
    )
