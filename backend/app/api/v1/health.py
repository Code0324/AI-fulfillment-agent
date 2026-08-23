"""API v1 health endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """Health check endpoint for API v1."""
    return {"status": "ok"}
