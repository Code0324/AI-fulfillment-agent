"""In-memory address processing service.

Provides address parsing, validation, and human review workflow.
All data lives only for the lifetime of the process.
No real customer PII is used — all test data is synthetic.
"""

import math
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.schemas.address import (
    AddressProcessingListResponse,
    AddressProcessingResult,
    AddressProcessingStatus,
    AddressReviewAction,
    AddressReviewRequest,
)
from app.services.address.processor import AddressProcessor, MockAddressProcessor


class AddressProcessingService:
    """In-memory store and operations for address processing."""

    def __init__(self, processor: AddressProcessor | None = None) -> None:
        self._results: dict[UUID, AddressProcessingResult] = {}
        self._processor = processor or MockAddressProcessor()

    def parse(self, raw_address: str) -> AddressProcessingResult:
        """Parse a raw address string using the configured processor."""
        result = self._processor.process(raw_address)
        self._results[result.id] = result
        return result

    def get(self, result_id: UUID) -> AddressProcessingResult:
        """Return one processing result by ID or raise NotFoundError."""
        result = self._results.get(result_id)
        if result is None:
            raise NotFoundError("Address processing result not found")
        return result

    def list_results(
        self,
        *,
        page: int = 1,
        page_size: int = 10,
        status: AddressProcessingStatus | None = None,
    ) -> AddressProcessingListResponse:
        """Return a paginated slice of processing results with optional filters."""
        all_results = list(self._results.values())
        if status is not None:
            all_results = [r for r in all_results if r.status == status]
        total_items = len(all_results)
        total_pages = math.ceil(total_items / page_size) if total_items else 0

        start = (page - 1) * page_size
        end = start + page_size
        items = all_results[start:end]

        return AddressProcessingListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    def review(
        self, result_id: UUID, request: AddressReviewRequest
    ) -> AddressProcessingResult:
        """Review and optionally correct a processing result."""
        result = self.get(result_id)

        if result.status == AddressProcessingStatus.PROCESSED and request.action == AddressReviewAction.APPROVE:
            raise ValidationError("Result is already processed — no review needed")

        if result.status == AddressProcessingStatus.FAILED and request.action == AddressReviewAction.APPROVE:
            raise ValidationError(
                "Cannot approve a failed result — use correct to fix issues"
            )

        now = datetime.now(timezone.utc)

        if request.action == AddressReviewAction.REJECT:
            updated = result.model_copy(
                update={
                    "status": AddressProcessingStatus.FAILED,
                    "review_reason": "Rejected during human review",
                    "updated_at": now,
                }
            )
            self._results[result_id] = updated
            return updated

        if request.action == AddressReviewAction.CORRECT:
            # Apply corrections
            updates = {"updated_at": now}
            if request.first_name is not None:
                updates["first_name"] = request.first_name
            if request.last_name is not None:
                updates["last_name"] = request.last_name
            if request.address_line_1 is not None:
                updates["address_line_1"] = request.address_line_1
            if request.address_line_2 is not None:
                updates["address_line_2"] = request.address_line_2
            if request.city is not None:
                updates["city"] = request.city
            if request.state is not None:
                updates["state"] = request.state
            if request.postal_code is not None:
                updates["postal_code"] = request.postal_code
            if request.country is not None:
                updates["country"] = request.country
            if request.phone is not None:
                updates["phone"] = request.phone

            updated = result.model_copy(update=updates)

            # Re-validate after correction
            required_fields = [
                updated.first_name,
                updated.last_name,
                updated.address_line_1,
                updated.city,
                updated.state,
                updated.postal_code,
                updated.country,
            ]
            filled_count = sum(1 for f in required_fields if f)
            confidence = filled_count / len(required_fields)
            updated.confidence = round(confidence, 2)

            if confidence >= 0.7:
                updated.status = AddressProcessingStatus.PROCESSED
                updated.review_reason = None
                updated.validation_issues = []
            else:
                updated.status = AddressProcessingStatus.NEEDS_REVIEW
                updated.review_reason = "Still missing required fields after correction"

            self._results[result_id] = updated
            return updated

        if request.action == AddressReviewAction.APPROVE:
            updated = result.model_copy(
                update={
                    "status": AddressProcessingStatus.PROCESSED,
                    "review_reason": None,
                    "validation_issues": [],
                    "confidence": 1.0,
                    "updated_at": now,
                }
            )
            self._results[result_id] = updated
            return updated

        # Should not reach here
        raise ValidationError(f"Unknown review action: {request.action}")

    def clear(self) -> None:
        """Remove all results (used by tests to reset state)."""
        self._results.clear()


address_processing_service = AddressProcessingService()
