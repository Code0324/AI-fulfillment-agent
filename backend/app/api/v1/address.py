"""API v1 address processing routes.

Provides endpoints for parsing, reviewing, and managing address processing.
All data is synthetic — no real customer PII is used.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status as http_status

from app.schemas.address import (
    AddressParseRequest,
    AddressProcessingListResponse,
    AddressProcessingResult,
    AddressProcessingStatus,
    AddressReviewRequest,
)
from app.services.address.service import address_processing_service

router = APIRouter(prefix="/address", tags=["address"])


@router.post(
    "/parse",
    response_model=AddressProcessingResult,
    status_code=http_status.HTTP_201_CREATED,
)
def parse_address(request: AddressParseRequest) -> AddressProcessingResult:
    """Parse a raw address string into structured fields.

    The processor normalizes the address, validates required fields,
    and assigns a confidence score. Addresses with low confidence
    or missing required fields are flagged for human review.
    """
    return address_processing_service.parse(request.raw_address)


@router.get("", response_model=AddressProcessingListResponse)
def list_results(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    status: AddressProcessingStatus | None = Query(
        None, description="Filter by processing status"
    ),
) -> AddressProcessingListResponse:
    """List address processing results with optional status filter."""
    return address_processing_service.list_results(
        page=page, page_size=page_size, status=status
    )


@router.get("/{result_id}", response_model=AddressProcessingResult)
def get_result(result_id: UUID) -> AddressProcessingResult:
    """Return a single address processing result."""
    return address_processing_service.get(result_id)


@router.post(
    "/{result_id}/review",
    response_model=AddressProcessingResult,
)
def review_result(
    result_id: UUID, request: AddressReviewRequest
) -> AddressProcessingResult:
    """Review, correct, or reject an address processing result.

    Actions:
    - approve: Mark a NEEDS_REVIEW result as processed
    - correct: Apply field corrections and re-validate
    - reject: Mark the result as failed
    """
    return address_processing_service.review(result_id, request)
