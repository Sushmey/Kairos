"""Heartbeat service — policy core with pluggable delivery."""

from __future__ import annotations

from kairos.core.context import read_context
from kairos.core.feedback import process_feedback
from kairos.core.ranking import evaluate_surface
from kairos.db.notifications import save_notification
from kairos.delivery.registry import deliver
from kairos.delivery.render import build_delivery_hints, ok_reason
from kairos.models.schemas import DeliveryMode, FeedbackAction, HeartbeatResult
from kairos.observability.bus import event_bus


class HeartbeatService:
    """Channel-agnostic heartbeat: decide → persist → deliver → return contract."""

    async def run(
        self,
        delivery: DeliveryMode = "auto",
        context_override: str | None = None,
    ) -> HeartbeatResult:
        activity: list[str] = ["heartbeat tick"]

        context = read_context()
        decision = await evaluate_surface(context, context_override)
        activity.append(
            f"gate: should_surface={decision.should_surface}"
            + (f" score={decision.adjusted_score:.2f}" if decision.adjusted_score else "")
        )

        if not decision.should_surface:
            reason = ok_reason(decision.gate_reasons)
            event_bus.emit("indicator", "KAIROS_OK", status="ok", reason=reason)
            return HeartbeatResult(
                status="KAIROS_OK",
                decision=decision,
                activity=activity,
                reason=reason,
            )

        notification = await save_notification(decision)
        activity.append(f"surfaced notification {notification.notification_id}")

        result = HeartbeatResult(
            status="SURFACE",
            decision=decision,
            notification=notification,
            activity=activity,
        )
        result.delivery = build_delivery_hints(result)

        mode: DeliveryMode = "auto" if delivery == "auto" else delivery
        await deliver(result, notification, mode)
        event_bus.emit("indicator", "SURFACE", status="alert")
        return result

    async def record_feedback(
        self,
        notification_id: str,
        action: FeedbackAction,
        *,
        url: str | None = None,
    ) -> dict:
        """Capture host-reported feedback → feedback_events + bandit update."""
        result = await process_feedback(notification_id, action, url=url)
        if result.get("status") == "ok":
            event_bus.emit(
                "feedback",
                f"Feedback recorded: {action}",
                notification_id=notification_id,
                action=action,
                bandit=result.get("bandit"),
            )
        return result


heartbeat_service = HeartbeatService()
