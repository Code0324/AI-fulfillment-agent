"""API v1 order routes — authenticated, organization-scoped, PostgreSQL-backed."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status as http_status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ValidationError
from app.database import get_db
from app.dependencies import get_current_organization
from app.models import Organization
from app.schemas.order import Order, OrderCreate, OrderListResponse, OrderStatus, OrderUpdate
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=http_status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Create a new fulfillment order for the authenticated organization.

    The organization is always derived server-side from the authenticated
    user's JWT — never from client input.
    """
    try:
        return await order_service.create_async(db, payload, organization.id)
    except IntegrityError as e:
        # The real idempotency guarantee for TikTok orders is the DB-level
        # UniqueConstraint on (organization_id, tiktok_order_id) — see
        # models.py. tiktok_ingestion.py already handles this gracefully
        # for the automated sync path (reports skipped_existing); this is
        # for anyone hitting this endpoint directly with a duplicate
        # tiktok_order_id, which should get a clear 409, not a raw 500.
        if payload.tiktok_order_id:
            raise ConflictError(
                f"An order with tiktok_order_id '{payload.tiktok_order_id}' already exists for this organization"
            ) from e
        raise


@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    status: OrderStatus | None = Query(None, description="Filter by order status"),
    search: str | None = Query(None, description="Search by customer, product, or order ID"),
    source: str | None = Query(None, description="Filter by order source: MANUAL, AMAZON, MOCK_AMAZON, or TIKTOK"),
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    """List orders for the authenticated organization only."""
    return await order_service.list_orders_async(
        db, organization.id, page=page, page_size=page_size, status=status, search=search, source=source
    )


@router.get("/{order_id}", response_model=Order)
async def get_order(
    order_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Return a single order by ID, scoped to the authenticated organization.

    An order belonging to a different organization behaves identically to a
    missing order (404) — existence is never leaked across tenants.
    """
    return await order_service.get_async(db, order_id, organization.id)


@router.patch("/{order_id}", response_model=Order)
async def update_order(
    order_id: UUID,
    payload: OrderUpdate,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Update the status of an existing order owned by the authenticated organization."""
    if payload.status is None:
        raise ValidationError("Field 'status' is required")
    return await order_service.update_status_async(
        db, order_id, payload.status, organization.id
    )


@router.post("/{order_id}/reserve", response_model=Order)
async def reserve_order_inventory(
    order_id: UUID,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Order:
    """Reserve inventory for an existing order owned by the authenticated organization."""
    return await order_service.reserve_inventory_async(db, order_id, organization.id)
