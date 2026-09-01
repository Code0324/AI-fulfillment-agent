"""API v1 TikTok Shop routes.

Provides status/connection-test endpoints for the TikTok Shop integration,
plus the order-ingestion endpoint that fetches real orders and persists
them into FulfillmentOrder (see services/tiktok_ingestion.py). SKU mapping
resolution and fulfillment happen downstream via the existing fulfillment
workflow engine — this router does not reimplement any of that.

CRITICAL SAFETY:
- Never fabricates a "configured" or "success" result
- Credentials never exposed to frontend
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.dependencies import get_current_organization
from app.models import Organization
from app.services import tiktok_ingestion
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tiktok", tags=["tiktok"])


@router.get("/status")
def get_tiktok_status():
    """Get TikTok Shop connection status.

    Returns:
        Connection status including whether credentials are configured,
        the active environment, and connection details. Never fabricates
        a "configured" result when credentials are absent.
    """
    tiktok_provider = provider_registry.get_tiktok_provider()

    if tiktok_provider is None:
        return {
            "configured": False,
            "environment": settings.tiktok_environment,
            "provider": None,
            "notice": "TikTok Shop is not configured/authorized — provider not registered",
        }

    status = tiktok_provider.connection_status
    return {
        **status,
        "provider": tiktok_provider.provider_name,
    }


@router.get("/test-connection")
def test_tiktok_connection():
    """Test connection to TikTok Shop.

    Returns:
        Connection test results — only ever reports success if a real
        token fetch actually succeeded.
    """
    tiktok_provider = provider_registry.get_tiktok_provider()

    if tiktok_provider is None:
        return {
            "success": False,
            "error": "TikTok Shop provider not configured",
            "environment": settings.tiktok_environment,
        }

    return tiktok_provider.test_connection()


@router.post("/sync")
async def sync_tiktok_orders(
    organization: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Fetch new orders from TikTok Shop and persist them.

    This is the automatic ingestion entry point — it fetches real orders
    (if configured), writes new ones to the database, best-effort syncs
    each to Google Sheets, and starts the existing fulfillment workflow
    for each (which stops at SKU-mapping review or human approval exactly
    as it always has). Never fabricates a "configured" or "synced" result.
    """
    return await tiktok_ingestion.sync_tiktok_orders_async(db, organization.id)
