"""Slack incoming-webhook notification provider — real integration.

Posts to a Slack "Incoming Webhook" URL (https://api.slack.com/messaging/webhooks).
Chosen over Slack's full Web API (OAuth, bot tokens, app installation) for
the same reason PA-API's signer is hand-rolled instead of pulling in an SDK:
this repo prefers the smallest real integration that actually works over a
heavier one, and an incoming webhook is the simplest genuinely-real way to
post an alert into a channel — one URL, one POST, no OAuth flow to run.

Never tested against a real Slack workspace in this repo (no webhook URL
available in this sandbox) — but unlike scrape_pricing.py, there is no
ToS/fragility caveat here: Slack's incoming-webhook contract is a small,
stable, documented JSON POST, not scraped HTML.
"""

import logging
from datetime import datetime, timezone

import httpx

from app.services.providers.notifications_base import (
    NotificationProviderBase,
    NotificationProviderNotConfiguredError,
    NotificationProviderRequestError,
)

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {"info": ":information_source:", "warning": ":warning:", "critical": ":rotating_light:"}


class SlackWebhookNotificationProvider(NotificationProviderBase):
    """Real Slack incoming-webhook notification provider.

    SAFETY:
    - is_configured requires a real webhook_url — never silently "sends"
      when unconfigured.
    - Never fabricates a sent=True result — only returned after Slack's
      API actually returns 200 with body "ok" (its documented success
      response for incoming webhooks).
    - The webhook URL itself is a credential (anyone with it can post to
      the channel) — never logged.
    """

    def __init__(self, webhook_url: str | None = None):
        from app.core.config import settings

        self._webhook_url = webhook_url if webhook_url is not None else settings.SLACK_WEBHOOK_URL

    @property
    def provider_name(self) -> str:
        return "slack_webhook_notification_provider"

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    def send(self, title: str, message: str, severity: str = "info") -> dict:
        if not self.is_configured:
            raise NotificationProviderNotConfiguredError(self.provider_name)

        emoji = SEVERITY_EMOJI.get(severity, SEVERITY_EMOJI["info"])
        payload = {"text": f"{emoji} *{title}*\n{message}"}

        try:
            with httpx.Client() as client:
                response = client.post(self._webhook_url, json=payload, timeout=15.0)
        except httpx.TimeoutException as e:
            raise NotificationProviderRequestError("Slack webhook request timed out", recoverable=True) from e
        except httpx.NetworkError as e:
            raise NotificationProviderRequestError(
                f"Slack webhook network error: {type(e).__name__}", recoverable=True
            ) from e

        if response.status_code != 200 or response.text.strip() != "ok":
            recoverable = response.status_code == 429 or response.status_code >= 500
            raise NotificationProviderRequestError(
                f"Slack webhook returned HTTP {response.status_code}: {response.text[:200]}",
                recoverable=recoverable,
            )

        return {
            "sent": True,
            "channel": "slack",
            "source": self.provider_name,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
