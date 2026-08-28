"""API v1 fulfillment routes.

Provides endpoints for the supplier fulfillment sandbox workflow.
All data is synthetic — no real Amazon, supplier, or customer data is used.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Query, status as http_status

from app.schemas.fulfillment import (
    FulfillmentAuditResponse,
    FulfillmentListResponse,
    FulfillmentWorkflow,
    StartFulfillmentRequest,
)
from app.services.fulfillment.workflow import fulfillment_engine

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


@router.post(
    "/{order_id}/start",
    response_model=FulfillmentWorkflow,
    status_code=http_status.HTTP_201_CREATED,
)
def start_fulfillment(
    order_id: UUID,
    request: StartFulfillmentRequest | None = None,
) -> FulfillmentWorkflow:
    """Start a fulfillment workflow for an order.

    Idempotent: If an active workflow exists for this order,
    returns the existing workflow.
    """
    shipping_method = request.shipping_method if request else "standard"
    return fulfillment_engine.start_workflow(order_id, shipping_method)


@router.get("", response_model=FulfillmentListResponse)
def list_workflows(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
) -> FulfillmentListResponse:
    """List fulfillment workflows."""
    all_workflows = fulfillment_engine.list_workflows()
    total_items = len(all_workflows)
    total_pages = math.ceil(total_items / page_size) if total_items else 0
    start = (page - 1) * page_size
    end = start + page_size
    items = all_workflows[start:end]

    return FulfillmentListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


@router.get("/{workflow_id}", response_model=FulfillmentWorkflow)
def get_workflow(workflow_id: UUID) -> FulfillmentWorkflow:
    """Return a single fulfillment workflow."""
    return fulfillment_engine.get_workflow(workflow_id)


@router.post("/{workflow_id}/approve", response_model=FulfillmentWorkflow)
def approve_workflow(workflow_id: UUID) -> FulfillmentWorkflow:
    """Approve a workflow waiting for human approval."""
    return fulfillment_engine.approve_workflow(workflow_id)


@router.post("/{workflow_id}/reject", response_model=FulfillmentWorkflow)
def reject_workflow(workflow_id: UUID) -> FulfillmentWorkflow:
    """Reject a workflow waiting for human approval."""
    return fulfillment_engine.reject_workflow(workflow_id)


@router.post("/{workflow_id}/cancel", response_model=FulfillmentWorkflow)
def cancel_workflow(workflow_id: UUID) -> FulfillmentWorkflow:
    """Cancel a workflow if its state allows cancellation."""
    return fulfillment_engine.cancel_workflow(workflow_id)


@router.post("/{workflow_id}/retry", response_model=FulfillmentWorkflow)
def retry_workflow(workflow_id: UUID) -> FulfillmentWorkflow:
    """Retry a failed/expired/cancelled workflow safely."""
    return fulfillment_engine.retry_workflow(workflow_id)


@router.get("/{workflow_id}/audit", response_model=FulfillmentAuditResponse)
def get_audit_log(
    workflow_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> FulfillmentAuditResponse:
    """Return audit events for a workflow."""
    events = fulfillment_engine.get_audit_log(workflow_id, page=page, page_size=page_size)
    return FulfillmentAuditResponse(events=events, total=len(events))
