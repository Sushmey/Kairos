"""Persist fused headspace snapshots per user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kairos.db.mongo import get_database
from kairos.models.schemas import ContextSnapshot

COLLECTION = "context_cache"
LEGACY_DOC_ID = "latest"


def _doc_id(user_id: str | None) -> str:
    return user_id or LEGACY_DOC_ID


async def ensure_context_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("updated_at")
    await db[COLLECTION].create_index("user_id")


async def save_context(snapshot: ContextSnapshot, *, user_id: str | None = None) -> None:
    await ensure_context_indexes()
    doc_id = _doc_id(user_id)
    payload: dict[str, Any] = {
        "_id": doc_id,
        "user_id": user_id,
        "snapshot": snapshot.model_dump(mode="json"),
        "updated_at": datetime.now(timezone.utc),
    }
    await get_database()[COLLECTION].replace_one({"_id": doc_id}, payload, upsert=True)


async def load_context(user_id: str | None = None) -> ContextSnapshot | None:
    doc_id = _doc_id(user_id)
    doc = await get_database()[COLLECTION].find_one({"_id": doc_id})
    if not doc or not doc.get("snapshot"):
        if user_id and doc_id != LEGACY_DOC_ID:
            legacy = await get_database()[COLLECTION].find_one({"_id": LEGACY_DOC_ID})
            if legacy and legacy.get("snapshot"):
                return ContextSnapshot.model_validate(legacy["snapshot"])
        return None
    return ContextSnapshot.model_validate(doc["snapshot"])
