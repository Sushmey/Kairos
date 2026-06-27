"""Render digests for host agents and delivery adapters."""

from __future__ import annotations

from kairos.config import settings
from kairos.models.schemas import ClusterDigest, DeliveryHints, HeartbeatResult


def digest_to_markdown(digest: ClusterDigest) -> str:
    lines = [
        f"## {digest.cluster_name} ({digest.member_count} bookmarks)",
        "",
        digest.summary,
        "",
        f"**Why now:** {digest.why_now}",
        "",
    ]
    for link in digest.links:
        label = link.get("label", link.get("url", "link"))
        mode = link.get("consumption_mode", "")
        suffix = f" — {mode}" if mode else ""
        lines.append(f"- [{label}]({link.get('url', '#')}){suffix}")
    return "\n".join(lines)


def build_delivery_hints(result: HeartbeatResult) -> DeliveryHints:
    """Build MCP/host-facing presentation hints for a SURFACE heartbeat."""
    digest = result.notification.digest if result.notification else None
    markdown = digest_to_markdown(digest) if digest else ""
    notification_id = result.notification.notification_id if result.notification else None
    dashboard_url = (
        f"{settings.web_base_url.rstrip('/')}/n/{notification_id}"
        if notification_id
        else None
    )

    actions: list[str] = []
    if digest:
        actions.append("Show the rendered_markdown digest to the user in chat.")
        if dashboard_url:
            actions.append(
                f"If the Kairos dashboard is running, direct the user to {dashboard_url}."
            )
            actions.append(
                "If the dashboard is not running, offer to start it with `kairos serve`."
            )
        actions.append(
            "Ask the user for feedback (relevant / snooze / dismiss) and call "
            "record_feedback with their response."
        )
        if settings.os_delivery_enabled:
            actions.append(
                "On macOS with os delivery enabled, optionally run terminal-notifier "
                "with a short summary if the user wants OS alerts."
            )

    return DeliveryHints(
        rendered_markdown=markdown,
        dashboard_url=dashboard_url,
        suggested_host_actions=actions,
        suppress_ok_in_chat=settings.mcp_suppress_ok_in_chat,
    )


def ok_reason(decision_gate_reasons: dict[str, bool]) -> str:
    failed = [k for k, passed in decision_gate_reasons.items() if not passed]
    if not failed:
        return "interrupt gate closed"
    return f"gate failed: {', '.join(failed)}"
