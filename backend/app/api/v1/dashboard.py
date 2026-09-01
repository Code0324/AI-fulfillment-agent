"""API v1 dashboard route — the AI Fulfillment Control Center summary."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_organization
from app.models import Organization
from app.services.dashboard_service import get_dashboard_summary_async

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Connection status, automation counts, recent activity, and the
    human-approval queue for the authenticated organization's TikTok
    orders. Computed entirely from real state — never fabricated."""
    return await get_dashboard_summary_async(db, organization.id)
