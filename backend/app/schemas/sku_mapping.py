"""SKU + variation mapping schemas.

See app/services/sku_mapping/engine.py for the matching rule these
statuses encode. Binding safety rule: a fuzzy match is never returned as
MATCHED regardless of confidence score — only an explicitly confirmed
mapping (services/sku_mapping/engine.py's create_explicit_mapping) can
ever be MATCHED. This prevents an uncertain automated guess from ever
silently resolving to the wrong product.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MappingStatus(str, Enum):
    """Status of a TikTok SKU + variation -> Amazon SKU/ASIN mapping."""

    MATCHED = "matched"  # Only ever set via an explicit, human-confirmed mapping
    NEEDS_REVIEW = "needs_review"  # A fuzzy suggestion exists but is not auto-applied
    NOT_FOUND = "not_found"  # No candidate at all
    CONFLICT = "conflict"  # Multiple, roughly-equally-plausible candidates


class MappingResult(BaseModel):
    """Result of resolving a TikTok SKU + variation to an Amazon SKU/ASIN."""

    tiktok_sku: str = Field(..., description="The TikTok SKU that was looked up")
    variation: str | None = Field(None, description="The TikTok variation that was looked up")
    amazon_sku: str | None = Field(
        None,
        description="Resolved Amazon SKU. Only trustworthy for fulfillment when status is MATCHED.",
    )
    asin: str | None = Field(
        None,
        description="Resolved Amazon ASIN. Only trustworthy for fulfillment when status is MATCHED.",
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Match confidence, 0.0-1.0")
    status: MappingStatus = Field(..., description="Mapping status")
    reason: str | None = Field(None, description="Human-readable explanation, especially for non-MATCHED statuses")
