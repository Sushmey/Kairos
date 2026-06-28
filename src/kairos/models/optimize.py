"""GEPA / prompt optimization result models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class GepaReadiness(BaseModel):
    feedback_count: int
    positive_count: int
    negative_count: int
    min_samples: int
    gepa_ready: bool
    days_window: int


class FixtureEvalCase(BaseModel):
    fixture: str
    passed: bool
    has_summary: bool
    has_why_now: bool
    has_links: bool


class FixtureEvalResult(BaseModel):
    status: Literal["ok", "skipped"]
    fixtures: int = 0
    passed: int = 0
    pass_rate: float = 0.0
    results: list[FixtureEvalCase] = Field(default_factory=list)
    prompt_override: bool = False
    reason: str | None = None


class GepaRunResult(BaseModel):
    """Summary returned by run_gepa and CLI optimize commands."""

    status: Literal["ok", "skipped", "dry_run"]
    reason: str | None = None
    sample_count: int | None = None
    min_samples: int | None = None
    readiness: GepaReadiness | None = None
    run_id: str | None = None
    engagement_before: float | None = None
    engagement_after: float | None = None
    engagement_delta: float | None = None
    prompt_before: str | None = None
    prompt_after: str | None = None
    diff_summary: str | None = None
    prompt_changed: bool | None = None
    fixture_eval_before: dict[str, Any] | None = None
    fixture_eval_after: dict[str, Any] | None = None
