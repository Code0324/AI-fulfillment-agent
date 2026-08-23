"""Generic API response and status schemas.

These are reusable building blocks for all API endpoints.
No domain-specific logic — just common structures that
future chunks will compose into Amazon/supplier schemas.
"""

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Generic status payload returned by health / status endpoints."""

    status: str = Field(..., description="Human-readable application status")


class PaginationMeta(BaseModel):
    """Metadata for paginated list responses (future use)."""

    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    per_page: int = Field(..., ge=1, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class ApiResponse(BaseModel):
    """Generic wrapper for API responses with optional data and error."""

    ok: bool = Field(..., description="Whether the request was successful")
    data: dict | list | None = Field(None, description="Response payload")
    error: str | None = Field(None, description="Error message when ok is false")
    meta: PaginationMeta | None = Field(None, description="Pagination info for list endpoints")
