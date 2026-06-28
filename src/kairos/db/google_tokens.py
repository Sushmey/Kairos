"""Per-user Google OAuth token storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database

COLLECTION = "google_connections"


async def ensure_google_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("email")
    await db[COLLECTION].create_index("updated_at")


async def save_google_connection(
    *,
    user_id: str,
    email: str,
    access_token: str,
    refresh_token: str,
    scopes: list[str],
    token_expiry: datetime | None = None,
) -> None:
    await ensure_google_indexes()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "scopes": scopes,
        "token_expiry": token_expiry,
        "updated_at": now,
        "created_at": now,
    }
    existing = await get_database()[COLLECTION].find_one({"_id": user_id})
    if existing:
        payload["created_at"] = existing.get("created_at", now)
    await get_database()[COLLECTION].replace_one({"_id": user_id}, payload, upsert=True)


async def load_google_connection(user_id: str) -> dict[str, Any] | None:
    return await get_database()[COLLECTION].find_one({"_id": user_id})


async def update_google_tokens(
    user_id: str,
    *,
    access_token: str,
    token_expiry: datetime | None = None,
) -> None:
    updates: dict[str, Any] = {
        "access_token": access_token,
        "updated_at": datetime.now(timezone.utc),
    }
    if token_expiry is not None:
        updates["token_expiry"] = token_expiry
    await get_database()[COLLECTION].update_one({"_id": user_id}, {"$set": updates})


async def delete_google_connection(user_id: str) -> bool:
    result = await get_database()[COLLECTION].delete_one({"_id": user_id})
    return result.deleted_count > 0


async def list_google_connections(limit: int = 50) -> list[dict[str, Any]]:
    cursor = get_database()[COLLECTION].find().sort("updated_at", -1).limit(limit)
    return await cursor.to_list(length=limit)
