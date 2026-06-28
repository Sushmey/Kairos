"""Human-readable log lines for the admin activity stream."""

from __future__ import annotations

from kairos.models.schemas import ContextSnapshot

_GATE_LABELS: dict[str, str] = {
    "daily_budget": "daily surface budget exhausted",
    "calendar_gap": "calendar gap too short",
    "min_gap": "too soon since last surface",
    "score_threshold": "relevance score below threshold",
    "moment_fit": "cluster does not fit this moment",
}


def describe_gate_failures(gate_reasons: dict[str, bool]) -> str:
    failed = [_GATE_LABELS.get(k, k.replace("_", " ")) for k, ok in gate_reasons.items() if not ok]
    if not failed:
        return "all interrupt gates passed"
    if len(failed) == 1:
        return failed[0]
    return ", ".join(failed[:-1]) + f", and {failed[-1]}"


def describe_headspace_read(context: ContextSnapshot) -> str:
    loc = context.location_type or "unknown location"
    parts = [f"Reading headspace — you are at {loc}"]
    if context.calendar_gap_minutes is not None:
        parts.append(f"{context.calendar_gap_minutes} min until the next meeting")
    if context.surfaces_today is not None:
        parts.append(f"{context.surfaces_today} surfaces today")
    if context.moment_narrative:
        snippet = context.moment_narrative.strip()
        if len(snippet) > 140:
            snippet = snippet[:137] + "…"
        parts.append(f'moment: "{snippet}"')
    return "; ".join(parts) + "."


def describe_headspace_update(context: ContextSnapshot) -> str:
    loc = context.location_type or "unknown location"
    return (
        f"Headspace snapshot saved — {loc}, "
        f"{context.surfaces_today} surfaces today, "
        f"{context.calendar_gap_minutes} min calendar gap."
    )


def describe_silence(reason: str) -> str:
    return f"Staying silent — {reason}."


def describe_surface(cluster_name: str | None = None) -> str:
    if cluster_name:
        return f"Decision: surface «{cluster_name}» to the user."
    return "Decision: surface a digest to the user."


def describe_ranking_complete(
    *,
    should_surface: bool,
    cluster_id: str | None,
    cluster_name: str | None,
    adjusted_score: float | None,
    gate_reasons: dict[str, bool],
) -> str:
    label = cluster_name or (cluster_id[:20] if cluster_id else None)
    if should_surface and label:
        score = f" (score {adjusted_score:.2f})" if adjusted_score is not None else ""
        return f"Ranking complete — surfacing «{label}»{score}."
    why = describe_gate_failures(gate_reasons)
    return f"Ranking complete — holding silence because {why}."
