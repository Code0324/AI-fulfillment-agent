"""Notification provider abstraction.

Backs the notifications MCP server (backend/mcp_servers/notifications/) —
alerting a human that a fulfillment workflow needs review (WAITING_APPROVAL
or FAILED — see services/fulfillment/workflow.py). Kept separate from
providers/base.py's order-provider contract for the same reason
pricing_base.py is: exactly ONE notification provider is active at a time,
chosen globally via NOTIFICATION_PROVIDER (see providers/registry.py), not
several order providers coexisting per order.source.

Every method must do exactly one of two things: genuinely deliver the
notification (or genuinely log it, for the "log" provider — see
mock/mock_notifications.py) and report the truth about that, or raise
NotificationProviderError. Never report sent=True without it actually
having happened.
"""

import abc
import logging

from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)


class NotificationProviderError(ProviderError):
    """Base error for notification provider failures."""


class NotificationProviderNotConfiguredError(NotificationProviderError):
    """The selected notification provider has no usable credentials/config."""

    def __init__(self, provider_name: str = "unknown"):
        super().__init__(
            f"Notification provider '{provider_name}' is not configured", recoverable=False
        )


class NotificationProviderRequestError(NotificationProviderError):
    """A request to the notification provider's real delivery channel
    failed (network error, API error, etc.)."""

    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message, recoverable=recoverable)


class NotificationProviderBase(abc.ABC):
    """Abstract base class for notification providers.

    Synchronous, matching every other provider method in this codebase —
    the MCP server calling this has no event loop of its own to speak of
    either (see mcp_servers/notifications/server.py).
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool:
        ...

    @abc.abstractmethod
    def send(self, title: str, message: str, severity: str = "info") -> dict:
        """Deliver one notification.

        Returns {"sent": True, "channel": <provider_name>, ...}. Raises
        NotificationProviderNotConfiguredError / NotificationProviderRequestError
        rather than ever returning sent=True for a notification that
        wasn't genuinely delivered (or, for the log provider, genuinely
        logged).
        """
        ...
