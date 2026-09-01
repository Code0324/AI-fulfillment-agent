"""API v1 SKU mapping routes.

Exposes the one HTTP action a human actually needs to perform in the
TikTok -> Amazon SKU bridge: confirming an explicit mapping when the
fulfillment workflow has stopped a TikTok order for SKU review (see
services/sku_mapping/engine.py — a fuzzy suggestion is never auto-applied,
only an explicit, human-confirmed mapping can unblock the workflow).

After confirming a mapping, call POST /api/v1/fulfillment/{workflow_id}/retry
(existing endpoint) to resume the order that was waiting on it — this
router does not re-run fulfillment itself.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_organization
from app.models import Organization
from app.services.sku_mapping.engine import create_explicit_mapping_async

router = APIRouter(prefix="/sku-mappings", tags=["sku-mappings"])


class SkuMappingCreate(BaseModel):
    """A human-confirmed TikTok SKU -> Amazon SKU/ASIN mapping."""

    tiktok_sku: str = Field(..., min_length=1, description="The TikTok SKU to resolve")
    variation: str | None = Field(None, description="TikTok variation (e.g. size/color), if any")
    amazon_sku: str = Field(..., min_length=1, description="The confirmed Amazon SKU")
    asin: str | None = Field(None, description="The confirmed Amazon ASIN, if known")


class SkuMappingOut(BaseModel):
    id: UUID
    tiktok_sku: str
    variation: str | None
    amazon_sku: str | None
    asin: str | None
    confidence_score: float
    status: str
    source: str


@router.post("", response_model=SkuMappingOut, status_code=http_status.HTTP_201_CREATED)
async def create_sku_mapping(
    payload: SkuMappingCreate,
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> SkuMappingOut:
    """Confirm a TikTok SKU -> Amazon SKU/ASIN mapping for the authenticated
    organization. This is the ONLY path that can produce a "matched"
    mapping — see services/sku_mapping/engine.py."""
    row = await create_explicit_mapping_async(
        payload.tiktok_sku,
        payload.variation,
        payload.amazon_sku,
        payload.asin,
        organization.id,
        db,
    )
    return SkuMappingOut(
        id=row.id,
        tiktok_sku=row.tiktok_sku,
        variation=row.variation,
        amazon_sku=row.amazon_sku,
        asin=row.asin,
        confidence_score=row.confidence_score,
        status=row.status,
        source=row.source,
    )
