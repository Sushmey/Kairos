"""Shared Pydantic models for Kairos data shapes."""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

HeartbeatStatus = Literal["KAIROS_OK", "SURFACE"]
DeliveryMode = Literal["auto", "return_only", "none"]
NotificationStatus = Literal["pending", "snoozed", "dismissed", "acted", "expired"]
FeedbackAction = Literal["expanded", "link_click", "snoozed", "dismissed", "acted", "ignored"]


class ContextSnapshot(BaseModel):
    """Live headspace vector at decision time (PLAN.md)."""

    upcoming_event_title: str | None = None
    recent_event_title: str | None = None
    post_meeting_minutes: int | None = None
    location_type: Literal[
        "desk", "commute", "gym", "cafe", "near_anchor", "unknown"
    ] = "unknown"

    calendar_gap_minutes: int = 0
    meeting_density_today: float = 0.0
    minutes_since_last_meeting: int = 0
    surfaces_today: int = 0
    time_since_last_surface_minutes: int = 0

    hour: int = Field(default_factory=lambda: datetime.now().hour)
    day_of_week: int = Field(default_factory=lambda: datetime.now().weekday())
    is_weekend: bool = False


class BookmarkEnrichment(BaseModel):
    """LLM-derived metadata for a bookmark at ingest."""

    topic_tags: list[str]
    consumption_mode: Literal["read-deep", "skim", "watch", "act-in-world", "save-to-project"]
    energy_cost: float = Field(ge=0.0, le=1.0)
    geo_anchor: str | None = None
    perishability: Literal["evergreen", "dated", "time-sensitive"] = "evergreen"


class BookmarkDocument(BaseModel):
    """Bookmark document stored in MongoDB (X API + optional enrichment)."""

    id: str | None = Field(default=None, alias="_id")
    x_tweet_id: str
    url: str
    raw_text: str
    author_id: str | None = None
    author_username: str | None = None
    tweet_created_at: datetime | None = None
    context_annotations: list[dict] = Field(default_factory=list)
    referenced_tweets: list[dict] = Field(default_factory=list)

    embedding: list[float] | None = None
    cluster_id: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    consumption_mode: Literal[
        "read-deep", "skim", "watch", "act-in-world", "save-to-project"
    ] | None = None
    energy_cost: float | None = Field(default=None, ge=0.0, le=1.0)
    geo_anchor: str | None = None
    geo_coords: list[float] | None = None
    perishability: Literal["evergreen", "dated", "time-sensitive"] | None = None

    ingested_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_surfaced_at: datetime | None = None
    surface_count: int = 0

    model_config = {"populate_by_name": True}


class ClusterDigest(BaseModel):
    """Topic cluster digest surfaced to the user."""

    cluster_id: str
    cluster_name: str
    summary: str
    why_now: str
    links: list[dict[str, str]]  # {url, label, consumption_mode}
    member_count: int


class SurfaceDecision(BaseModel):
    """Result of the ranking pipeline + interrupt gate."""

    should_surface: bool
    cluster_id: str | None = None
    digest: ClusterDigest | None = None
    gate_reasons: dict[str, bool] = Field(default_factory=dict)
    adjusted_score: float | None = None
    context: ContextSnapshot | None = None


class NotificationRecord(BaseModel):
    """Canonical persisted surface event (delivery adapters fan out from this)."""

    notification_id: str = Field(default_factory=lambda: str(uuid4()))
    cluster_id: str | None = None
    digest: ClusterDigest | None = None
    context_snapshot: ContextSnapshot | None = None
    status: NotificationStatus = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


class DeliveryHints(BaseModel):
    """Instructions for host agents (MCP clients) on how to present a surface."""

    rendered_markdown: str = ""
    dashboard_url: str | None = None
    suggested_host_actions: list[str] = Field(default_factory=list)
    suppress_ok_in_chat: bool = True


class HeartbeatResult(BaseModel):
    """Structured heartbeat contract — same shape for HTTP, MCP, and Antigravity."""

    status: HeartbeatStatus
    decision: SurfaceDecision
    notification: NotificationRecord | None = None
    delivery: DeliveryHints | None = None
    activity: list[str] = Field(default_factory=list)
    reason: str | None = None


class FeedbackRequest(BaseModel):
    """Host-reported interaction with a surfaced digest."""

    notification_id: str
    action: FeedbackAction
    url: str | None = None
