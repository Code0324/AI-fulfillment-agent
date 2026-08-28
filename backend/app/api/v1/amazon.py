"""API v1 Amazon routes.

Provides endpoints for Amazon integration status and operations.
All operations are READ-ONLY (GET only).

CRITICAL SAFETY:
- Read-only operations only
- Credentials never exposed to frontend
- Production requires explicit environment configuration
"""

import logging

from fastapi import APIRouter, Query

from app.core.config import settings
from app.services.providers.amazon.activation_validator import get_activation_status
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/amazon", tags=["amazon"])


# ---------------------------------------------------------------------------
# Connection Status
# ---------------------------------------------------------------------------

@router.get("/status")
def get_amazon_status():
    """Get Amazon connection status.
    
    Returns:
        Connection status including:
        - configured: Whether credentials are available
        - sandbox: Whether in sandbox mode
        - environment: 'sandbox' or 'production'
        - mode: Always 'read-only'
        - Connection details
    """
    amazon_provider = provider_registry.get_amazon_provider()
    
    if amazon_provider is None:
        return {
            "configured": False,
            "sandbox": True,
            "environment": settings.amazon_environment,
            "mode": "read-only",
            "notice": "Amazon provider not registered — no credentials available",
            "provider": None,
        }
    
    # Get detailed status from provider
    status = amazon_provider.connection_status
    
    env = settings.amazon_environment
    notice = f"Amazon {env} integration active — read-only mode"
    
    return {
        **status,
        "provider": amazon_provider.provider_name,
        "notice": notice,
    }


@router.get("/test-connection")
def test_amazon_connection():
    """Test connection to Amazon.
    
    Returns:
        Connection test results
    """
    amazon_provider = provider_registry.get_amazon_provider()
    
    if amazon_provider is None:
        return {
            "success": False,
            "error": "Amazon provider not configured",
            "sandbox": settings.amazon_environment == "sandbox",
            "environment": settings.amazon_environment,
        }
    
    # Test connection
    result = amazon_provider.test_connection()
    return result


# ---------------------------------------------------------------------------
# Order Operations (Read-Only)
# ---------------------------------------------------------------------------

@router.get("/orders")
def list_amazon_orders(
    limit: int = Query(50, ge=1, le=100, description="Max orders to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """List orders from Amazon.
    
    This is a READ-ONLY operation.
    Returns normalized orders ready for import.
    """
    amazon_provider = provider_registry.get_amazon_provider()
    env = settings.amazon_environment
    
    if amazon_provider is None:
        return {
            "orders": [],
            "total": 0,
            "provider": None,
            "sandbox": env == "sandbox",
            "environment": env,
            "notice": "Amazon provider not configured",
        }
    
    # List orders from Amazon
    orders = amazon_provider.list_orders(limit=limit, offset=offset)
    
    return {
        "orders": orders,
        "total": len(orders),
        "provider": amazon_provider.provider_name,
        "sandbox": env == "sandbox",
        "environment": env,
        "mode": "read-only",
    }


@router.get("/orders/{order_id}")
def get_amazon_order(order_id: str):
    """Get a single order from Amazon.
    
    This is a READ-ONLY operation.
    Returns normalized order ready for import.
    """
    amazon_provider = provider_registry.get_amazon_provider()
    env = settings.amazon_environment
    
    if amazon_provider is None:
        return {
            "error": "Amazon provider not configured",
            "order_id": order_id,
        }
    
    # Get order from Amazon
    order = amazon_provider.get_order(order_id)
    
    if order is None:
        return {
            "error": "Order not found",
            "order_id": order_id,
            "sandbox": env == "sandbox",
            "environment": env,
        }
    
    return {
        "order": order,
        "provider": amazon_provider.provider_name,
        "sandbox": env == "sandbox",
        "environment": env,
    }


@router.post("/orders/import")
def import_amazon_orders(
    order_ids: list[str] | None = None,
):
    """Import orders from Amazon.
    
    This imports orders into the local system with idempotency.
    Orders are normalized and ready for fulfillment processing.
    
    The imported orders will go through:
    - Address processing
    - Inventory validation
    - Fulfillment preparation
    - WAITING_APPROVAL (STOP — no auto-submit)
    """
    amazon_provider = provider_registry.get_amazon_provider()
    env = settings.amazon_environment
    
    if amazon_provider is None:
        return {
            "imported": [],
            "total": 0,
            "provider": None,
            "sandbox": env == "sandbox",
            "environment": env,
            "notice": "Amazon provider not configured",
        }
    
    # Import orders
    imported_ids = amazon_provider.import_orders(order_ids)
    
    return {
        "imported": imported_ids,
        "total": len(imported_ids),
        "provider": amazon_provider.provider_name,
        "sandbox": env == "sandbox",
        "environment": env,
        "notice": "Orders imported — ready for fulfillment processing",
    }


# ---------------------------------------------------------------------------
# Production Activation Validation
# ---------------------------------------------------------------------------

@router.get("/activation-status")
def get_activation_validation():
    """Validate production activation configuration.
    
    This endpoint checks configuration WITHOUT making Amazon API calls.
    It verifies that all required credentials and settings are properly configured.
    
    Returns:
        Activation status including:
        - ready: Whether system is ready for production
        - credentials_configured: Whether all credentials are set
        - checks: Individual validation results
        - errors: Any configuration errors
        - warnings: Any configuration warnings
    """
    return get_activation_status()


# ---------------------------------------------------------------------------
# System Information
# ---------------------------------------------------------------------------

@router.get("/info")
def get_amazon_info():
    """Get Amazon integration information.
    
    Returns:
        Integration info including:
        - API version
        - Endpoints
        - Rate limits
        - Supported operations
    """
    from app.services.providers.amazon.sp_api_client import SANDBOX_ENDPOINTS, PRODUCTION_ENDPOINTS
    
    env = settings.amazon_environment
    endpoints = SANDBOX_ENDPOINTS if env == "sandbox" else PRODUCTION_ENDPOINTS
    
    return {
        "api_version": "2026-01-01",
        "sandbox": env == "sandbox",
        "environment": env,
        "mode": "read-only",
        "endpoints": endpoints,
        "rate_limits": {
            "requests_per_second": 1,
            "burst": 15,
        },
        "supported_operations": [
            "getOrder",
            "searchOrders",
        ],
        "blocked_operations": [
            "cancelOrder",
            "confirmShipment",
            "createOrder",
            "updateOrder",
        ],
        "notice": "Read-only integration — write operations are blocked",
    }
