"""Kairos agent harness — Google ADK orchestration layer."""

from __future__ import annotations

import logging
import os
import uuid

from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from kairos.agent.agent import APP_NAME, build_root_agent, pop_last_heartbeat
from kairos.agent.mcp_auth import warm_google_mcp_auth
from kairos.agent.prompts import DECISION_TURN_PROMPT
from kairos.config import settings
from kairos.core.heartbeat import heartbeat_service
from kairos.google.credentials import GoogleAuthError
from kairos.models.schemas import DeliveryMode, HeartbeatResult, SurfaceDecision
from kairos.observability.bus import event_bus

logger = logging.getLogger(__name__)

if settings.gemini_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

_session_service = InMemorySessionService()


def _resolve_user_id(user_id: str | None = None) -> str:
    uid = user_id or settings.kairos_user_id
    if uid:
        return uid
    if settings.google_refresh_token:
        return "env_user"
    return "anonymous"


async def _run_agent_turn(
    prompt: str,
    *,
    user_id: str | None = None,
) -> tuple[str, HeartbeatResult | None]:
    uid = _resolve_user_id(user_id)
    try:
        await warm_google_mcp_auth(uid if uid != "env_user" else None)
    except GoogleAuthError as exc:
        logger.warning("Google MCP auth skipped: %s", exc)

    agent = build_root_agent()
    app = App(name=APP_NAME, root_agent=agent)
    runner = Runner(app=app, session_service=_session_service)

    session = await _session_service.create_session(
        app_name=APP_NAME,
        user_id=uid,
        session_id=str(uuid.uuid4()),
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=uid,
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.author == agent.name and event.content:
            parts = event.content.parts or []
            chunk = "".join(p.text or "" for p in parts if hasattr(p, "text"))
            if chunk:
                final_text = chunk

    return final_text, pop_last_heartbeat()


async def run_decision_cycle(
    delivery: DeliveryMode = "auto",
    context_override: str | None = None,
    user_id: str | None = None,
) -> HeartbeatResult:
    """Execute one heartbeat via policy core (direct path, no agent loop)."""
    event_bus.emit("session", "Heartbeat cycle started.")
    result = await heartbeat_service.run(
        delivery=delivery,
        context_override=context_override,
        user_id=user_id,
    )
    if result.status == "SURFACE":
        cluster = result.notification.digest.cluster_name if result.notification and result.notification.digest else "cluster"
        event_bus.emit("session", f"Heartbeat finished — surfaced «{cluster}».", status=result.status)
    else:
        reason = result.reason or "nothing worth interrupting"
        event_bus.emit("session", f"Heartbeat finished — silent ({reason}).", status=result.status)
    return result


async def run_decision_cycle_via_agent(
    user_id: str | None = None,
) -> HeartbeatResult:
    """Execute one heartbeat via the ADK agent harness (Workspace MCP sensor fusion)."""
    event_bus.emit("session", "Agent heartbeat started — running ADK turn.")
    text, heartbeat = await _run_agent_turn(DECISION_TURN_PROMPT, user_id=user_id)
    logger.info("Agent heartbeat complete: %s", (text or "")[:200])
    if heartbeat is None:
        heartbeat = HeartbeatResult(
            status="KAIROS_OK",
            decision=SurfaceDecision(should_surface=False),
            reason="agent did not invoke run_heartbeat",
            activity=[(text or "no agent output")[:200]],
        )
    status = heartbeat.status
    event_bus.emit(
        "session",
        f"Agent heartbeat finished ({status}).",
        preview=(text or "")[:300],
        status=status,
    )
    return heartbeat


async def run_interactive(prompt: str, user_id: str | None = None) -> str:
    """Run a single interactive turn (for MCP / Claude Code parity)."""
    text, _ = await _run_agent_turn(prompt, user_id=user_id)
    return text or ""
