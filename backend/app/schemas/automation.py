"""Automation schemas for browser-based workflow foundation.

Represents mock/demo automation for sandbox testing only.
NOT connected to real Amazon, suppliers, or external services.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Normalized Address
# ---------------------------------------------------------------------------

class NormalizedAddress(BaseModel):
    """Reusable normalized address structure for form filling."""

    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")
    address_line_1: str = Field(..., min_length=1, description="Address line 1")
    address_line_2: str = Field(default="", description="Address line 2")
    city: str = Field(..., min_length=1, description="City")
    state: str = Field(..., min_length=1, description="State or province")
    postal_code: str = Field(..., min_length=1, description="Postal or ZIP code")
    country: str = Field(default="US", description="Country code")
    phone: str = Field(default="", description="Phone number")


# ---------------------------------------------------------------------------
# Automation Session
# ---------------------------------------------------------------------------

class AutomationEnvironment(str, Enum):
    """Automation environment type."""

    SANDBOX = "sandbox"
    PRODUCTION = "production"


class AutomationAction(str, Enum):
    """Types of automation actions."""

    NAVIGATE = "navigate"
    READ = "read"
    EXTRACT = "extract"
    FILL = "fill"
    SELECT = "select"
    CLICK = "click"
    VERIFY = "verify"
    SCREENSHOT = "screenshot"
    SUBMIT = "submit"


class AutomationActionRisk(str, Enum):
    """Risk level for automation actions."""

    SAFE = "safe"
    HIGH_RISK = "high_risk"


# Risk classification for actions
ACTION_RISK_MAP: dict[AutomationAction, AutomationActionRisk] = {
    AutomationAction.NAVIGATE: AutomationActionRisk.SAFE,
    AutomationAction.READ: AutomationActionRisk.SAFE,
    AutomationAction.EXTRACT: AutomationActionRisk.SAFE,
    AutomationAction.FILL: AutomationActionRisk.SAFE,
    AutomationAction.SELECT: AutomationActionRisk.SAFE,
    AutomationAction.CLICK: AutomationActionRisk.SAFE,
    AutomationAction.VERIFY: AutomationActionRisk.SAFE,
    AutomationAction.SCREENSHOT: AutomationActionRisk.SAFE,
    AutomationAction.SUBMIT: AutomationActionRisk.HIGH_RISK,
}


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------

class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    """An approval request for a high-risk action."""

    id: UUID = Field(..., description="Unique approval request identifier")
    session_id: UUID = Field(..., description="Associated automation session")
    action: AutomationAction = Field(..., description="Action requiring approval")
    description: str = Field(..., description="Human-readable description")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Current status")
    created_at: datetime = Field(..., description="When the request was created")
    resolved_at: datetime | None = Field(None, description="When the request was resolved")


class ApprovalResponse(BaseModel):
    """Response to an approval request."""

    status: ApprovalStatus = Field(..., description="Approval decision")


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditResult(str, Enum):
    """Result of an audit event."""

    SUCCESS = "success"
    FAILURE = "failure"
    PENDING_APPROVAL = "pending_approval"
    CANCELLED = "cancelled"


class AuditEvent(BaseModel):
    """Structured audit event for automation actions."""

    id: UUID = Field(..., description="Unique event identifier")
    session_id: UUID = Field(..., description="Associated automation session")
    timestamp: datetime = Field(..., description="When the event occurred")
    action: AutomationAction = Field(..., description="Action performed")
    environment: AutomationEnvironment = Field(..., description="Environment")
    result: AuditResult = Field(..., description="Action result")
    approval_status: ApprovalStatus | None = Field(None, description="Approval status if applicable")
    error_message: str | None = Field(None, description="Error message if failed")
    details: str = Field(default="", description="Non-sensitive details")


# ---------------------------------------------------------------------------
# Automation Session
# ---------------------------------------------------------------------------

class AutomationSessionStatus(str, Enum):
    """Status of an automation session."""

    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class AutomationSession(BaseModel):
    """An automation session tracking browser workflow state."""

    id: UUID = Field(..., description="Unique session identifier")
    environment: AutomationEnvironment = Field(default=AutomationEnvironment.SANDBOX, description="Environment")
    status: AutomationSessionStatus = Field(default=AutomationSessionStatus.IDLE, description="Session status")
    current_action: str | None = Field(None, description="Current action being performed")
    last_result: str | None = Field(None, description="Last action result")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="When the session was created")
    updated_at: datetime = Field(..., description="When the session was last updated")


class SessionListResponse(BaseModel):
    """Paginated response for session list endpoints."""

    items: list[AutomationSession] = Field(..., description="Page of sessions")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of sessions")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


# ---------------------------------------------------------------------------
# Form Fill Request
# ---------------------------------------------------------------------------

class FormFillRequest(BaseModel):
    """Request to fill a form using normalized address data."""

    session_id: UUID = Field(..., description="Automation session ID")
    address: NormalizedAddress = Field(..., description="Address to fill")
    shipping_method: str = Field(default="standard", description="Shipping method to select")


class FormFillResult(BaseModel):
    """Result of a form fill operation."""

    session_id: UUID = Field(..., description="Automation session ID")
    success: bool = Field(..., description="Whether the fill succeeded")
    filled_fields: list[str] = Field(default_factory=list, description="Fields that were filled")
    screenshot_path: str | None = Field(None, description="Path to screenshot if captured")
    error_message: str | None = Field(None, description="Error message if failed")
