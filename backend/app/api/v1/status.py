"""API v1 status endpoint.

Returns application status to verify that the schema layer
is wired up correctly. This is a development/test endpoint.
"""

from fastapi import APIRouter

from app.schemas.status import AppStatus

router = APIRouter()


@router.get("/status", response_model=AppStatus)
def get_status() -> AppStatus:
    """Return application status."""
    return AppStatus(status="ok")
