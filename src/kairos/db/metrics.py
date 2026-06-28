"""Engagement metrics aggregated from feedback_events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from kairos.db.bandit import bandit_user_id
from kairos.db.mongo import get_database

COLLECTION = "feedback_events"


def _user_match(user_id: str | None, *, include_sim: bool = False) -> dict[str, Any]:
    uid = bandit_user_id(user_id)
    if include_sim and uid == "__default__":
        # Demo gym aggregate — personas use sim:* user_ids
        return {"sim": True}
    return {"user_id": uid}


async def get_engagement_by_day(
    days: int = 14,
    persona: str | None = None,
    include_sim: bool = True,
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return daily engagement rates over the last `days` days.

    Each entry: {date: "YYYY-MM-DD", surfaces: int, engagements: int, rate: float}
    Ordered oldest → newest so the dashboard sparkline reads left-to-right.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    match_filter: dict[str, Any] = {"created_at": {"$gte": since}, **_user_match(user_id, include_sim=include_sim)}
    if not include_sim:
        match_filter["sim"] = {"$ne": True}
    if persona:
        match_filter["persona"] = persona

    pipeline = [
        {"$match": match_filter},
        {
            "$group": {
                "_id": {
                    "$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}
                },
                "surfaces": {"$sum": 1},
                "engagements": {
                    "$sum": {
                        "$cond": [
                            {"$gt": ["$derived_reward", 0]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"_id": 1}},
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "surfaces": 1,
                "engagements": 1,
                "rate": {
                    "$cond": [
                        {"$gt": ["$surfaces", 0]},
                        {"$divide": ["$engagements", "$surfaces"]},
                        0.0,
                    ]
                },
            }
        },
    ]

    cursor = get_database()[COLLECTION].aggregate(pipeline)
    return await cursor.to_list(length=days + 5)


async def get_overall_stats(
    include_sim: bool = True,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return aggregate counts: total surfaces, engagements, overall rate."""
    match_filter: dict[str, Any] = _user_match(user_id, include_sim=include_sim)
    if not include_sim:
        match_filter["sim"] = {"$ne": True}

    pipeline = [
        {"$match": match_filter},
        {
            "$group": {
                "_id": None,
                "total_surfaces": {"$sum": 1},
                "total_engagements": {
                    "$sum": {
                        "$cond": [
                            {"$gt": ["$derived_reward", 0]},
                            1,
                            0,
                        ]
                    }
                },
            }
        },
    ]

    results = await get_database()[COLLECTION].aggregate(pipeline).to_list(length=1)
    if not results:
        return {"total_surfaces": 0, "total_engagements": 0, "overall_rate": 0.0}

    row = results[0]
    surfaces = row.get("total_surfaces", 0)
    engagements = row.get("total_engagements", 0)
    return {
        "total_surfaces": surfaces,
        "total_engagements": engagements,
        "overall_rate": engagements / surfaces if surfaces else 0.0,
    }


def rate_change_pct(by_day: list[dict[str, Any]]) -> float | None:
    """Week-over-week change in engagement rate (percent points)."""
    if len(by_day) < 2:
        return None
    mid = len(by_day) // 2
    first = by_day[:mid]
    second = by_day[mid:]
    if not first or not second:
        return None

    def _avg_rate(rows: list[dict[str, Any]]) -> float:
        rates = [float(r.get("rate") or 0.0) for r in rows if r.get("surfaces")]
        if not rates:
            return 0.0
        return sum(rates) / len(rates)

    earlier = _avg_rate(first)
    recent = _avg_rate(second)
    if earlier == 0:
        return round(recent * 100, 1) if recent else None
    return round((recent - earlier) / earlier * 100, 1)
