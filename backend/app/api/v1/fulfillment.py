"""API v1 fulfillment routes.

Provides endpoints for the supplier fulfillment sandbox workflow.
All data is synthetic — no real Amazon, supplier, or customer data is used.

APPROVAL SECURITY (binding requirement):
The fulfillment engine itself is per-process/in-memory and has no concept
of "organization" — it only knows order_id/workflow_id. Tenant isolation
and RBAC are enforced here, at the API boundary, for every route:
  - get_current_organization resolves the caller's org from their JWT —
    never from client-supplied input.
  - _verify_order_ownership / _verify_workflow_ownership re-fetch the
    order from the database scoped to that organization_id and 404 if it
    doesn't match — a workflow whose order belongs to a different
    organization behaves exactly like a nonexistent workflow.
  - require_permission enforces RBAC per action (read vs execute vs
    approve), using the same Permission enum orders.py's routes would use.
No endpoint ever trusts a client-supplied "approved"/"organization_id"
value — approval state is derived entirely from the authenticated
session and the workflow's own server-side state machine.
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_organization, require_permission
from app.models import Organization
from app.schemas.fulfillment import (
    FulfillmentAuditResponse,
    FulfillmentListResponse,
    FulfillmentWorkflow,
    StartFulfillmentRequest,
)
from app.services import order_service
from app.services.fulfillment.workflow import fulfillment_engine

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


async def _verify_order_ownership(db: AsyncSession, order_id: UUID, organization: Organization) -> None:
    """Raise NotFoundError (-> 404) if this order doesn't belong to the
    authenticated organization. Never leaks whether an order exists under
    a different organization."""
    await order_service.get_async(db, order_id, organization.id)


async def _verify_workflow_ownership(
    db: AsyncSession, workflow_id: UUID, organization: Organization
) -> FulfillmentWorkflow:
    workflow = fulfillment_engine.get_workflow(workflow_id)
    await _verify_order_ownership(db, workflow.order_id, organization)
    return workflow


@router.post(
    "/{order_id}/start",
    response_model=FulfillmentWorkflow,
    status_code=http_status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fulfillment:execute"))],
)
async def start_fulfillment(
    order_id: UUID,
    request: StartFulfillmentRequest | None = None,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Start a fulfillment workflow for an order owned by the authenticated
    organization.

    Idempotent: If an active workflow exists for this order,
    returns the existing workflow.
    """
    await _verify_order_ownership(db, order_id, organization)
    shipping_method = request.shipping_method if request else "standard"
    return fulfillment_engine.start_workflow(order_id, shipping_method)


@router.get(
    "",
    response_model=FulfillmentListResponse,
    dependencies=[Depends(require_permission("fulfillment:read"))],
)
async def list_workflows(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentListResponse:
    """List fulfillment workflows belonging to the authenticated organization only."""
    org_orders = await order_service.list_orders_async(db, organization.id, page=1, page_size=1000)
    org_order_ids = {o.id for o in org_orders.items}
    all_workflows = [w for w in fulfillment_engine.list_workflows() if w.order_id in org_order_ids]
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


@router.get(
    "/{workflow_id}",
    response_model=FulfillmentWorkflow,
    dependencies=[Depends(require_permission("fulfillment:read"))],
)
async def get_workflow(
    workflow_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Return a single fulfillment workflow owned by the authenticated organization."""
    return await _verify_workflow_ownership(db, workflow_id, organization)


@router.post(
    "/{workflow_id}/approve",
    response_model=FulfillmentWorkflow,
    dependencies=[Depends(require_permission("fulfillment:approve"))],
)
async def approve_workflow(
    workflow_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Approve a workflow waiting for human approval.

    This is the FINAL IRREVERSIBLE ACTION gate. The request body carries
    no "approved" flag or organization_id to trust — approval is granted
    purely because THIS authenticated, permission-checked, org-verified
    request reached this line. fulfillment_engine.approve_workflow() then
    re-validates the workflow's own state machine (must be
    WAITING_APPROVAL, not expired) before doing anything irreversible.
    """
    await _verify_workflow_ownership(db, workflow_id, organization)
    return fulfillment_engine.approve_workflow(workflow_id)


@router.post(
    "/{workflow_id}/reject",
    response_model=FulfillmentWorkflow,
    dependencies=[Depends(require_permission("fulfillment:approve"))],
)
async def reject_workflow(
    workflow_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Reject a workflow waiting for human approval."""
    await _verify_workflow_ownership(db, workflow_id, organization)
    return fulfillment_engine.reject_workflow(workflow_id)


@router.post(
    "/{workflow_id}/cancel",
    response_model=FulfillmentWorkflow,
    dependencies=[Depends(require_permission("fulfillment:execute"))],
)
async def cancel_workflow(
    workflow_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Cancel a workflow if its state allows cancellation."""
    await _verify_workflow_ownership(db, workflow_id, organization)
    return fulfillment_engine.cancel_workflow(workflow_id)


@router.post(
    "/{workflow_id}/retry",
    response_model=FulfillmentWorkflow,
    dependencies=[Depends(require_permission("fulfillment:execute"))],
)
async def retry_workflow(
    workflow_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentWorkflow:
    """Retry a failed/expired/cancelled workflow safely."""
    await _verify_workflow_ownership(db, workflow_id, organization)
    return fulfillment_engine.retry_workflow(workflow_id)


@router.get(
    "/{workflow_id}/audit",
    response_model=FulfillmentAuditResponse,
    dependencies=[Depends(require_permission("fulfillment:read"))],
)
async def get_audit_log(
    workflow_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> FulfillmentAuditResponse:
    """Return audit events for a workflow owned by the authenticated organization."""
    await _verify_workflow_ownership(db, workflow_id, organization)
    events = fulfillment_engine.get_audit_log(workflow_id, page=page, page_size=page_size)
    return FulfillmentAuditResponse(events=events, total=len(events))
