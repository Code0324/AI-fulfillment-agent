"""Schemas for health-check responses."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Standard health-check response body."""

    status: str
