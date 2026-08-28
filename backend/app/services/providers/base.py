"""Base provider abstractions and safety configuration.

Defines the contracts that all providers must implement.
All providers are LOCAL/MOCK implementations only.
No real external services are connected.
"""

import abc
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safety Configuration
# ---------------------------------------------------------------------------

class ProviderEnvironment(str, Enum):
    """Provider environment type."""
    MOCK = "mock"
    SANDBOX = "sandbox"
    PRODUCTION = "production"


# Global safety flag — prevents accidental production usage
MOCK_ONLY: bool = True

def ensure_mock_mode() -> None:
    """Verify we're in mock mode. Raises if production is attempted."""
    if not MOCK_ONLY:
        raise RuntimeError(
            "Production providers are not enabled. "
            "Set MOCK_ONLY=True or use mock providers only."
        )


# ---------------------------------------------------------------------------
# Provider Operation Risk Classification
# ---------------------------------------------------------------------------

class ProviderOperationRisk(str, Enum):
    """Risk level for provider operations."""
    SAFE = "safe"
    HIGH_RISK = "high_risk"


# ---------------------------------------------------------------------------
# Provider Capability Flags
# ---------------------------------------------------------------------------

@dataclass
class ProviderCapabilities:
    """What a provider supports."""
    supports_order_read: bool = False
    supports_order_list: bool = False
    supports_supplier_prepare: bool = False
    supports_supplier_verify: bool = False
    supports_supplier_submit: bool = False
    supports_tracking_read: bool = False


# ---------------------------------------------------------------------------
# Base Provider
# ---------------------------------------------------------------------------

class BaseProvider(abc.ABC):
    """Abstract base class for all providers."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abc.abstractmethod
    def environment(self) -> ProviderEnvironment:
        """Provider environment."""
        ...

    @property
    @abc.abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """What this provider supports."""
        ...

    @property
    def is_mock(self) -> bool:
        """Whether this is a mock provider."""
        return self.environment in (ProviderEnvironment.MOCK, ProviderEnvironment.SANDBOX)


# ---------------------------------------------------------------------------
# Provider Errors
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base provider error."""
    def __init__(self, message: str = "Provider error", recoverable: bool = True):
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


class ProviderUnavailableError(ProviderError):
    """Provider is not available."""
    def __init__(self, provider_name: str = "unknown"):
        super().__init__(f"Provider '{provider_name}' is unavailable", recoverable=False)


class ProviderOperationNotSupportedError(ProviderError):
    """Provider does not support this operation."""
    def __init__(self, operation: str, provider_name: str = "unknown"):
        super().__init__(
            f"Operation '{operation}' not supported by provider '{provider_name}'",
            recoverable=False,
        )


class ProviderValidationError(ProviderError):
    """Provider validation failed."""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, recoverable=True)


class ProviderSubmissionBlockedError(ProviderError):
    """Provider submission blocked (approval required or duplicate)."""
    def __init__(self, reason: str = "Submission blocked"):
        super().__init__(reason, recoverable=False)


class ProviderAuthenticationError(ProviderError):
    """Provider authentication required (should not happen in mock mode)."""
    def __init__(self, provider_name: str = "unknown"):
        super().__init__(
            f"Authentication required for provider '{provider_name}' — "
            f"this should not happen in mock/sandbox mode",
            recoverable=False,
        )
