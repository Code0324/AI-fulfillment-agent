"""Log Notification Provider — the safe default notification channel.

Lives alongside this repo's other mock/ providers because it makes no
external network call, same as them — but unlike a synthetic-data mock, it
performs a genuine, real action every time send() is called: writing a
real log line — and truthfully reports exactly that (channel="log"), never
claiming to have reached a human being (no email sent, no Slack message
posted). That's exactly why NOTIFICATION_PROVIDER defaults to this rather
than a real channel — see app/core/config.py.
"""

import logging
from datetime import datetime, timezone

from app.services.providers.notifications_base import NotificationProviderBase

logger = logging.getLogger("app.notifications")


class LogNotificationProvider(NotificationProviderBase):
    """Writes notifications to the application log. Always configured —
    there is nothing to configure."""

    @property
    def provider_name(self) -> str:
        return "log_notification_provider"

    @property
    def is_configured(self) -> bool:
        return True

    def send(self, title: str, message: str, severity: str = "info") -> dict:
        log_fn = {"critical": logger.error, "warning": logger.warning}.get(severity, logger.info)
        log_fn("NOTIFICATION [%s] %s: %s", severity.upper(), title, message)
        return {
            "sent": True,
            "channel": "log",
            "source": self.provider_name,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }


log_notification_provider = LogNotificationProvider()
