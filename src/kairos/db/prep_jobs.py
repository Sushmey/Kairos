"""Background bookmark prep jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from kairos.db.mongo import get_database
from kairos.models.jobs import PrepJobParams, PrepJobRecord, PrepJobResult, PrepJobStatus

COLLECTION = "prep_jobs"


def _parse_prep_job(doc: dict[str, Any]) -> PrepJobRecord:
    doc = dict(doc)
    doc.pop("_id", None)
    params = doc.get("params") or {}
    result = doc.get("result")
    return PrepJobRecord(
        job_id=str(doc["job_id"]),
        status=doc.get("status", "pending"),
        params=PrepJobParams.model_validate(params),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        result=PrepJobResult.model_validate(result) if result else None,
        error=doc.get("error"),
    )


async def ensure_prep_job_indexes() -> None:
    db = get_database()
    await db[COLLECTION].create_index("job_id", unique=True)
    await db[COLLECTION].create_index([("created_at", -1)])


async def create_prep_job(*, params: PrepJobParams | dict[str, Any] | None = None) -> PrepJobRecord:
    await ensure_prep_job_indexes()
    parsed = PrepJobParams.model_validate(params or {})
    job_id = str(uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        "job_id": job_id,
        "status": "pending",
        "params": parsed.model_dump(mode="json"),
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    await get_database()[COLLECTION].insert_one(doc)
    return _parse_prep_job(doc)


async def update_prep_job(
    job_id: str,
    *,
    status: PrepJobStatus | None = None,
    result: PrepJobResult | dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    fields: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if status is not None:
        fields["status"] = status
    if result is not None:
        if isinstance(result, PrepJobResult):
            fields["result"] = result.model_dump(mode="json")
        else:
            fields["result"] = result
    if error is not None:
        fields["error"] = error
    await get_database()[COLLECTION].update_one({"job_id": job_id}, {"$set": fields})


async def get_prep_job(job_id: str) -> PrepJobRecord | None:
    doc = await get_database()[COLLECTION].find_one({"job_id": job_id})
    if not doc:
        return None
    return _parse_prep_job(doc)
