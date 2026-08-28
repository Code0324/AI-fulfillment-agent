"""API v1 mock Amazon routes.

Provides endpoints for the synthetic Amazon order import sandbox.
ALL DATA IS SYNTHETIC — NO REAL AMAZON ACCESS.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status as http_status
from pydantic import BaseModel, Field

from app.dependencies import get_current_organization
from app.models import Organization
from app.services.mock_amazon import mock_amazon_service

router = APIRouter(prefix="/mock-amazon", tags=["mock-amazon"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class MockAmazonImportResponse(BaseModel):
    """Response for mock Amazon order import."""
    imported: int = Field(..., description="Number of newly imported orders")
    skipped_duplicates: int = Field(..., description="Number of duplicate orders skipped")
    total_amazon_orders: int = Field(..., description="Total synthetic Amazon orders available")
    imported_order_ids: list[str] = Field(..., description="List of imported order IDs")


class MockAmazonStartFulfillmentRequest(BaseModel):
    """Request to start fulfillment for a mock Amazon order."""
    shipping_method: str = Field(default="standard", description="Shipping method")


class MockAmazonStartFulfillmentResponse(BaseModel):
    """Response for starting fulfillment."""
    amazon_order_id: str = Field(..., description="Mock Amazon order ID")
    workflow_id: str = Field(..., description="Internal workflow ID")
    status: str = Field(..., description="Workflow status")
    steps_completed: int = Field(..., description="Steps completed so far")
    total_steps: int = Field(..., description="Total workflow steps")


class MockAmazonOrderResponse(BaseModel):
    """Response for a single mock Amazon order."""
    amazon_order_id: str = Field(..., description="Mock Amazon order ID")
    internal_order_id: str = Field(..., description="Internal order ID")
    sku: str = Field(..., description="Product SKU")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., description="Quantity ordered")
    customer_name: str = Field(..., description="Customer name")
    status: str = Field(..., description="Order status")
    inventory_reserved: bool = Field(..., description="Whether inventory is reserved")
    fulfillment_status: str | None = Field(None, description="Fulfillment workflow status")
    source: str = Field(..., description="Data source (MOCK_AMAZON)")


class MockAmazonTrackingResponse(BaseModel):
    """Response for mock tracking generation."""
    amazon_order_id: str = Field(..., description="Mock Amazon order ID")
    tracking_id: str = Field(..., description="Synthetic tracking ID")
    carrier: str = Field(..., description="Mock carrier name")
    status: str = Field(..., description="Tracking status")
    message: str = Field(..., description="Safety notice")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/import",
    response_model=MockAmazonImportResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def import_mock_orders(
    organization: Organization = Depends(get_current_organization),
) -> MockAmazonImportResponse:
    """Import synthetic Amazon orders into the system.

    Loads local mock data, validates, and avoids duplicates.
    Never contacts the internet. The imported orders are owned by the
    authenticated caller's real organization — there is no default/system
    organization; the synthetic Amazon data is the only thing that's mock
    here, not the ownership.
    """
    result = mock_amazon_service.import_mock_orders(organization.id)
    return MockAmazonImportResponse(**result)


@router.get("/status")
def get_import_status() -> dict:
    """Return current import status and statistics."""
    return mock_amazon_service.get_import_status()


@router.get("/orders")
def list_imported_orders() -> list[MockAmazonOrderResponse]:
    """List all imported mock Amazon orders with their status."""
    orders = mock_amazon_service.get_imported_orders()
    return [MockAmazonOrderResponse(**o) for o in orders]


@router.post(
    "/{amazon_order_id}/fulfill",
    response_model=MockAmazonStartFulfillmentResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def start_fulfillment(
    amazon_order_id: str,
    request: MockAmazonStartFulfillmentRequest | None = None,
) -> MockAmazonStartFulfillmentResponse:
    """Start fulfillment workflow for a specific mock Amazon order.

    Idempotent: if a workflow already exists, returns the existing one.
    """
    shipping_method = request.shipping_method if request else "standard"
    result = mock_amazon_service.start_fulfillment(amazon_order_id, shipping_method)
    return MockAmazonStartFulfillmentResponse(**result)


@router.get("/{amazon_order_id}/fulfillment")
def get_fulfillment_status(amazon_order_id: str) -> dict:
    """Get fulfillment status for a specific mock Amazon order."""
    return mock_amazon_service.get_fulfillment_status(amazon_order_id)


@router.post(
    "/{amazon_order_id}/tracking",
    response_model=MockAmazonTrackingResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def generate_tracking(amazon_order_id: str) -> MockAmazonTrackingResponse:
    """Generate synthetic tracking for a completed mock Amazon order."""
    result = mock_amazon_service.generate_mock_tracking(amazon_order_id)
    return MockAmazonTrackingResponse(**result)


@router.get("/{amazon_order_id}/audit")
def get_audit_log(amazon_order_id: str) -> dict:
    """Return audit events for a specific mock Amazon order."""
    events = mock_amazon_service.get_audit_log(amazon_order_id)
    return {"events": events, "total": len(events)}
