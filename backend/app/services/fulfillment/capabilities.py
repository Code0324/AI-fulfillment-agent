"""Minimal fulfillment capability pattern.

Inspired by Digital-FTE's capability architecture but implemented
independently with no dependencies on that project.
All capabilities are lightweight, in-memory, and sandbox-only.
"""

import abc
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CapabilityType(str, Enum):
    """Whether a capability reads or writes data."""

    READ = "read"
    WRITE = "write"


@dataclass
class CapabilityDescriptor:
    """Declarative metadata for a capability."""

    name: str
    display_name: str
    description: str
    capability_type: CapabilityType
    requires_approval: bool = False


class BaseCapability(abc.ABC):
    """Abstract base class for fulfillment capabilities."""

    @property
    @abc.abstractmethod
    def descriptor(self) -> CapabilityDescriptor:
        """Return the capability's metadata."""
        ...

    @abc.abstractmethod
    def execute(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the capability."""
        ...

    @property
    def name(self) -> str:
        return self.descriptor.name

    @property
    def requires_approval(self) -> bool:
        return self.descriptor.requires_approval


class FulfillmentCapabilityRegistry:
    """Central registry for fulfillment capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, BaseCapability] = {}

    def register(self, capability: BaseCapability) -> None:
        """Register a capability."""
        desc = capability.descriptor
        if desc.name in self._capabilities:
            logger.warning("Overwriting capability: %s", desc.name)
        self._capabilities[desc.name] = capability
        logger.debug("Registered capability: %s", desc.name)

    def get(self, name: str) -> BaseCapability | None:
        """Get a capability by name."""
        return self._capabilities.get(name)

    def list_all(self) -> list[CapabilityDescriptor]:
        """List all registered capabilities."""
        return [cap.descriptor for cap in self._capabilities.values()]

    def has_capability(self, name: str) -> bool:
        """Check if a capability exists."""
        return name in self._capabilities


# Global registry instance
fulfillment_registry = FulfillmentCapabilityRegistry()
