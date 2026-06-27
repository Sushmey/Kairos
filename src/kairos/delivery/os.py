"""OS-native delivery — best-effort, platform-gated."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess

from kairos.models.schemas import HeartbeatResult, NotificationRecord

logger = logging.getLogger(__name__)


class OSDeliveryAdapter:
    name = "os"

    async def deliver(self, result: HeartbeatResult, notification: NotificationRecord) -> None:
        if not notification.digest:
            return

        title = notification.digest.cluster_name
        message = notification.digest.why_now
        system = platform.system()

        try:
            if system == "Darwin" and shutil.which("terminal-notifier"):
                subprocess.run(
                    ["terminal-notifier", "-title", title, "-message", message],
                    check=False,
                    capture_output=True,
                )
            elif system == "Linux" and shutil.which("notify-send"):
                subprocess.run(["notify-send", title, message], check=False, capture_output=True)
            else:
                logger.debug("No OS notification adapter available on %s", system)
        except OSError as exc:
            logger.warning("OS delivery failed: %s", exc)
