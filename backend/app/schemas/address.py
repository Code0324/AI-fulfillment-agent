"""Address processing schemas.

Represents the AI address processing foundation for fulfillment workflows.
All test data is synthetic — no real customer PII is used.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Processing Status
# ---------------------------------------------------------------------------

class AddressProcessingStatus(str, Enum):
    """Status of an address processing result."""

    PENDING = "pending"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Validation Issue
# ---------------------------------------------------------------------------

class ValidationSeverity(str, Enum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    """A single validation issue found during address processing."""

    field: str = Field(..., description="Field with the issue")
    message: str = Field(..., description="Description of the issue")
    severity: ValidationSeverity = Field(..., description="Issue severity")


# ---------------------------------------------------------------------------
# Address Processing Result
# ---------------------------------------------------------------------------

class AddressProcessingResult(BaseModel):
    """Result of processing a raw address through the address processor."""

    id: UUID = Field(..., description="Unique processing result identifier")
    raw_address: str = Field(..., description="Original raw address input")
    first_name: str = Field(default="", description="Extracted first name")
    last_name: str = Field(default="", description="Extracted last name")
    address_line_1: str = Field(default="", description="Extracted address line 1")
    address_line_2: str = Field(default="", description="Extracted address line 2")
    city: str = Field(default="", description="Extracted city")
    state: str = Field(default="", description="Extracted state or province")
    postal_code: str = Field(default="", description="Extracted postal or ZIP code")
    country: str = Field(default="", description="Normalized country code")
    phone: str = Field(default="", description="Extracted phone number")
    status: AddressProcessingStatus = Field(
        default=AddressProcessingStatus.PENDING,
        description="Processing status",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    validation_issues: list[ValidationIssue] = Field(
        default_factory=list, description="Validation issues found"
    )
    review_reason: str | None = Field(
        None, description="Reason human review is needed"
    )
    created_at: datetime = Field(..., description="When the result was created")
    updated_at: datetime = Field(..., description="When the result was last updated")


# ---------------------------------------------------------------------------
# Address Processing Request
# ---------------------------------------------------------------------------

class AddressParseRequest(BaseModel):
    """Request to parse a raw address string."""

    raw_address: str = Field(
        ..., min_length=1, description="Raw address string to process"
    )


# ---------------------------------------------------------------------------
# Address Review Request
# ---------------------------------------------------------------------------

class AddressReviewAction(str, Enum):
    """Action taken during human review."""

    APPROVE = "approve"
    CORRECT = "correct"
    REJECT = "reject"


class AddressReviewRequest(BaseModel):
    """Request to review/correct a processing result."""

    action: AddressReviewAction = Field(..., description="Review action")
    first_name: str | None = Field(None, description="Corrected first name")
    last_name: str | None = Field(None, description="Corrected last name")
    address_line_1: str | None = Field(None, description="Corrected address line 1")
    address_line_2: str | None = Field(None, description="Corrected address line 2")
    city: str | None = Field(None, description="Corrected city")
    state: str | None = Field(None, description="Corrected state")
    postal_code: str | None = Field(None, description="Corrected postal code")
    country: str | None = Field(None, description="Corrected country")
    phone: str | None = Field(None, description="Corrected phone")


# ---------------------------------------------------------------------------
# List Response
# ---------------------------------------------------------------------------

class AddressProcessingListResponse(BaseModel):
    """Paginated response for address processing list endpoints."""

    items: list[AddressProcessingResult] = Field(
        ..., description="Page of processing results"
    )
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of results")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
