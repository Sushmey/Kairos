"""Short-lived OAuth CSRF state tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.db.mongo import get_database

COLLECTION = "oauth_states"
TTL_SECONDS = 600


async def ensure_oauth_state_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("created_at", expireAfterSeconds=TTL_SECONDS)


async def save_oauth_state(state: str) -> None:
    await ensure_oauth_state_indexes()
    await get_database()[COLLECTION].insert_one(
        {
            "_id": state,
            "created_at": datetime.now(timezone.utc),
        }
    )


async def consume_oauth_state(state: str) -> bool:
    doc = await get_database()[COLLECTION].find_one_and_delete({"_id": state})
    return doc is not None
