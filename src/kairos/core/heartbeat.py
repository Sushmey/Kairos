"""Heartbeat service — policy core with pluggable delivery."""

from __future__ import annotations

from kairos.core.context import get_context_async, write_context
from kairos.core.fatigue import apply_surface_fatigue, refresh_fatigue_fields
from kairos.core.feedback import process_feedback
from kairos.core.intelligence import prepare_context_for_decision
from kairos.core.ranking import evaluate_surface
from kairos.db.notifications import save_notification
from kairos.delivery.registry import deliver
from kairos.delivery.render import build_delivery_hints, ok_reason
from kairos.models.schemas import DeliveryMode, FeedbackAction, HeartbeatResult
from kairos.observability.bus import event_bus
from kairos.observability.narrate import (
    describe_headspace_read,
    describe_headspace_update,
    describe_silence,
    describe_surface,
)


class HeartbeatService:
    """Channel-agnostic heartbeat: decide → persist → deliver → return contract."""

    async def run(
        self,
        delivery: DeliveryMode = "auto",
        context_override: str | None = None,
        user_id: str | None = None,
    ) -> HeartbeatResult:
        activity: list[str] = ["heartbeat tick"]

        context = await get_context_async(user_id)
        event_bus.emit(
            "context",
            describe_headspace_read(context),
            user_id=user_id,
            context=context.model_dump(mode="json"),
        )
        refreshed = refresh_fatigue_fields(context)
        if refreshed.model_dump() != context.model_dump():
            context = refreshed
            await write_context(context, user_id=user_id)
            event_bus.emit(
                "pipeline",
                f"Refreshed fatigue counters — {context.surfaces_today} surfaces delivered today.",
                surfaces_today=context.surfaces_today,
            )
        prior_narrative = context.moment_narrative
        context = await prepare_context_for_decision(context)
        if context.moment_narrative and context.moment_narrative != prior_narrative:
            await write_context(context, user_id=user_id)
            snippet = context.moment_narrative.strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "…"
            event_bus.emit(
                "pipeline",
                f"Cached a fresh moment narrative for ranking: \"{snippet}\"",
            )
        activity.append("intelligence: context prepared")
        event_bus.emit("pipeline", "Starting ranking pipeline — load clusters, match moment, run gates.")
        decision = await evaluate_surface(context, context_override, user_id=user_id)
        activity.append(
            f"gate: should_surface={decision.should_surface}"
            + (f" score={decision.adjusted_score:.2f}" if decision.adjusted_score else "")
        )

        if not decision.should_surface:
            reason = ok_reason(decision.gate_reasons)
            event_bus.emit("indicator", describe_silence(reason), status="ok", reason=reason)
            return HeartbeatResult(
                status="KAIROS_OK",
                decision=decision,
                activity=activity,
                reason=reason,
            )

        notification = await save_notification(decision, user_id=user_id)
        activity.append(f"surfaced notification {notification.notification_id}")
        cluster_name = decision.digest.cluster_name if decision.digest else None
        event_bus.emit(
            "pipeline",
            f"Saved notification {notification.notification_id[:8]}… for cluster "
            f"«{cluster_name or notification.cluster_id or 'unknown'}».",
            notification_id=notification.notification_id,
            cluster_id=notification.cluster_id,
        )

        context = apply_surface_fatigue(context)
        await write_context(context, user_id=user_id)
        activity.append(f"fatigue: surfaces_today={context.surfaces_today}")
        event_bus.emit(
            "pipeline",
            f"Applied surface fatigue — {context.surfaces_today} of today's budget used.",
            surfaces_today=context.surfaces_today,
        )

        result = HeartbeatResult(
            status="SURFACE",
            decision=decision,
            notification=notification,
            activity=activity,
        )
        result.delivery = build_delivery_hints(result)

        mode: DeliveryMode = "auto" if delivery == "auto" else delivery
        await deliver(result, notification, mode)
        event_bus.emit(
            "indicator",
            describe_surface(cluster_name),
            status="alert",
            cluster_name=cluster_name,
        )
        return result

    async def record_feedback(
        self,
        notification_id: str,
        action: FeedbackAction,
        *,
        url: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Capture host-reported feedback → feedback_events + bandit update."""
        result = await process_feedback(
            notification_id, action, url=url, user_id=user_id
        )
        if result.get("status") == "ok":
            bandit = result.get("bandit") or {}
            alpha = bandit.get("alpha")
            beta = bandit.get("beta")
            bandit_note = ""
            if alpha is not None and beta is not None:
                bandit_note = f" Bandit now α={alpha:.1f}, β={beta:.1f}."
            event_bus.emit(
                "feedback",
                f"User marked notification {notification_id[:8]}… as {action}.{bandit_note}",
                notification_id=notification_id,
                action=action,
                bandit=bandit,
            )
        return result


heartbeat_service = HeartbeatService()
