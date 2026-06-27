"""FastAPI web gateway — SSE activity stream, inbox, feedback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from kairos.agent.harness import run_decision_cycle
from kairos.core.heartbeat import heartbeat_service
from kairos.db.bandit import ensure_bandit_indexes, list_bandit_params
from kairos.db.mongo import close_mongo
from kairos.db.notifications import list_notifications
from kairos.models.schemas import FeedbackRequest
from kairos.observability.bus import event_bus

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Kairos", version="0.1.0")


class HeartbeatRequest(BaseModel):
    context_override: str | None = None


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    if out.get("_id"):
        out["id"] = str(out.pop("_id"))
    for key in ("created_at", "updated_at", "last_updated"):
        if out.get(key) and hasattr(out[key], "isoformat"):
            out[key] = out[key].isoformat()
    return out


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/stream")
async def stream_events() -> StreamingResponse:
    async def generate():
        async for event in event_bus.stream():
            yield event.to_sse()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/notifications")
async def get_notifications(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        docs = await list_notifications(limit=limit)
        return [_serialize(d) for d in docs]
    finally:
        await close_mongo()


@app.get("/api/bandit")
async def get_bandit_params(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        await ensure_bandit_indexes()
        docs = await list_bandit_params(limit=limit)
        return [_serialize(d) for d in docs]
    finally:
        await close_mongo()


@app.post("/api/heartbeat")
async def post_heartbeat(body: HeartbeatRequest | None = None) -> dict[str, Any]:
    override = body.context_override if body else None
    result = await run_decision_cycle(delivery="auto", context_override=override)
    return result.model_dump(mode="json")


@app.post("/api/feedback")
async def post_feedback(body: FeedbackRequest) -> dict[str, Any]:
    result = await heartbeat_service.record_feedback(
        body.notification_id,
        body.action,
        url=body.url,
    )
    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail=result.get("message", "feedback failed"))
    return result


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
