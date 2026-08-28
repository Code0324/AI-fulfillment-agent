"""Fulfillment workflow schemas.

Represents the end-to-end supplier fulfillment sandbox workflow.
All data is synthetic — no real Amazon, supplier, or customer data is used.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fulfillment Status
# ---------------------------------------------------------------------------

APPROVAL_EXPIRY_SECONDS = 3600  # 1 hour


class FulfillmentStatus(str, Enum):
    """Status of a fulfillment workflow."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# Valid state transitions
VALID_TRANSITIONS: dict[FulfillmentStatus, list[FulfillmentStatus]] = {
    FulfillmentStatus.PENDING: [FulfillmentStatus.RUNNING, FulfillmentStatus.CANCELLED],
    FulfillmentStatus.RUNNING: [
        FulfillmentStatus.WAITING_APPROVAL,
        FulfillmentStatus.COMPLETED,
        FulfillmentStatus.FAILED,
        FulfillmentStatus.CANCELLED,
    ],
    FulfillmentStatus.WAITING_APPROVAL: [
        FulfillmentStatus.APPROVED,
        FulfillmentStatus.CANCELLED,
        FulfillmentStatus.EXPIRED,
    ],
    FulfillmentStatus.APPROVED: [
        FulfillmentStatus.RUNNING,
        FulfillmentStatus.CANCELLED,
    ],
    FulfillmentStatus.COMPLETED: [],  # Terminal state — no transitions
    FulfillmentStatus.FAILED: [FulfillmentStatus.RUNNING, FulfillmentStatus.CANCELLED],
    FulfillmentStatus.CANCELLED: [FulfillmentStatus.RUNNING],  # Allow retry from cancelled
    FulfillmentStatus.EXPIRED: [FulfillmentStatus.RUNNING, FulfillmentStatus.CANCELLED],
}


def is_valid_transition(current: FulfillmentStatus, target: FulfillmentStatus) -> bool:
    """Check if a state transition is valid."""
    return target in VALID_TRANSITIONS.get(current, [])


# ---------------------------------------------------------------------------
# Fulfillment Step
# ---------------------------------------------------------------------------

class FulfillmentStepStatus(str, Enum):
    """Status of a single fulfillment step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"


class FulfillmentStep(BaseModel):
    """A single step in the fulfillment workflow."""

    name: str = Field(..., description="Step name")
    description: str = Field(default="", description="Step description")
    status: FulfillmentStepStatus = Field(
        default=FulfillmentStepStatus.PENDING, description="Step status"
    )
    result: str | None = Field(None, description="Step result message")
    error: str | None = Field(None, description="Error message if failed")
    started_at: datetime | None = Field(None, description="When step started")
    completed_at: datetime | None = Field(None, description="When step completed")


# ---------------------------------------------------------------------------
# Supplier Order Payload
# ---------------------------------------------------------------------------

class SupplierOrderPayload(BaseModel):
    """Payload for the mock supplier order."""

    sku: str = Field(..., description="Product SKU")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., ge=1, description="Quantity")
    first_name: str = Field(..., description="Customer first name")
    last_name: str = Field(..., description="Customer last name")
    address_line_1: str = Field(..., description="Address line 1")
    address_line_2: str = Field(default="", description="Address line 2")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    postal_code: str = Field(..., description="Postal code")
    country: str = Field(default="US", description="Country")
    phone: str = Field(default="", description="Phone")
    shipping_method: str = Field(default="standard", description="Shipping method")


# ---------------------------------------------------------------------------
# Fulfillment Confirmation
# ---------------------------------------------------------------------------

class FulfillmentConfirmation(BaseModel):
    """Confirmation of a mock supplier order submission."""

    confirmation_id: str = Field(..., description="Synthetic confirmation ID")
    supplier: str = Field(default="MOCK SUPPLIER", description="Supplier name")
    status: str = Field(default="submitted", description="Order status")
    submitted_at: datetime = Field(..., description="When submitted")
    estimated_delivery: str = Field(default="5-7 business days", description="Estimated delivery")


# ---------------------------------------------------------------------------
# Fulfillment Workflow
# ---------------------------------------------------------------------------

class FulfillmentWorkflow(BaseModel):
    """End-to-end fulfillment workflow state."""

    id: UUID = Field(..., description="Unique workflow identifier")
    order_id: UUID = Field(..., description="Associated order ID")
    status: FulfillmentStatus = Field(
        default=FulfillmentStatus.PENDING, description="Workflow status"
    )
    steps: list[FulfillmentStep] = Field(
        default_factory=list, description="Workflow steps"
    )
    current_step: int = Field(default=0, description="Index of current step")
    supplier_payload: SupplierOrderPayload | None = Field(
        None, description="Prepared supplier order"
    )
    confirmation: FulfillmentConfirmation | None = Field(
        None, description="Supplier confirmation"
    )
    approval_request_id: UUID | None = Field(
        None, description="Pending approval request ID"
    )
    approval_requested_at: datetime | None = Field(
        None, description="When approval was requested"
    )
    approval_expires_at: datetime | None = Field(
        None, description="When approval expires"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")
    error_message: str | None = Field(None, description="Error if failed")
    created_at: datetime = Field(..., description="When workflow was created")
    updated_at: datetime = Field(..., description="When workflow was last updated")

    @property
    def is_approval_expired(self) -> bool:
        """Check if approval has expired."""
        if self.approval_expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.approval_expires_at

    @property
    def can_retry(self) -> bool:
        """Check if workflow can be retried."""
        return self.status in (
            FulfillmentStatus.FAILED,
            FulfillmentStatus.EXPIRED,
            FulfillmentStatus.CANCELLED,
        )


# ---------------------------------------------------------------------------
# API Request/Response
# ---------------------------------------------------------------------------

class StartFulfillmentRequest(BaseModel):
    """Request to start a fulfillment workflow."""

    shipping_method: str = Field(
        default="standard", description="Shipping method"
    )


class FulfillmentListResponse(BaseModel):
    """Paginated response for fulfillment list endpoints."""

    items: list[FulfillmentWorkflow] = Field(
        ..., description="Page of workflows"
    )
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of workflows")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


# ---------------------------------------------------------------------------
# Audit Event
# ---------------------------------------------------------------------------

class FulfillmentAuditEvent(BaseModel):
    """Structured audit event for fulfillment reliability."""

    id: UUID = Field(..., description="Unique event identifier")
    workflow_id: UUID = Field(..., description="Associated workflow ID")
    order_id: UUID = Field(..., description="Associated order ID")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="When the event occurred")
    details: str = Field(default="", description="Non-sensitive details")
    error_message: str | None = Field(None, description="Error if failed")


class FulfillmentAuditResponse(BaseModel):
    """Response for audit log endpoints."""

    events: list[FulfillmentAuditEvent] = Field(
        ..., description="Audit events"
    )
    total: int = Field(..., ge=0, description="Total events")
