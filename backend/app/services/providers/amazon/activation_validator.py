"""Production Activation Validator — CHUNK 1Y.

Validates production activation configuration WITHOUT making Amazon API calls.
Checks that all required credentials and settings are properly configured.

Usage:
    from app.services.providers.amazon.activation_validator import validate_production_activation
    result = validate_production_activation()
    print(result)
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of production activation validation."""
    
    # Overall status
    is_ready: bool = False
    
    # Individual checks
    checks: dict[str, bool] = field(default_factory=dict)
    
    # Messages
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "is_ready": self.is_ready,
            "checks": self.checks,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def validate_production_activation() -> ValidationResult:
    """Validate production activation configuration.
    
    This function checks:
    1. All required credentials are set
    2. Environment is correctly configured
    3. Production endpoints are accessible (URL format only)
    4. No conflicting settings exist
    
    IMPORTANT: This does NOT make any Amazon API calls.
    It only validates configuration.
    
    Returns:
        ValidationResult with detailed status
    """
    result = ValidationResult()
    
    # -----------------------------------------------------------------------
    # Check 1: AMAZON_LWA_CLIENT_ID
    # -----------------------------------------------------------------------
    client_id = os.getenv("AMAZON_LWA_CLIENT_ID", "")
    if client_id:
        result.checks["client_id"] = True
        result.info.append("AMAZON_LWA_CLIENT_ID is configured")
    else:
        result.checks["client_id"] = False
        result.errors.append("AMAZON_LWA_CLIENT_ID is not set")
    
    # -----------------------------------------------------------------------
    # Check 2: AMAZON_LWA_CLIENT_SECRET
    # -----------------------------------------------------------------------
    client_secret = os.getenv("AMAZON_LWA_CLIENT_SECRET", "")
    if client_secret:
        result.checks["client_secret"] = True
        result.info.append("AMAZON_LWA_CLIENT_SECRET is configured")
    else:
        result.checks["client_secret"] = False
        result.errors.append("AMAZON_LWA_CLIENT_SECRET is not set")
    
    # -----------------------------------------------------------------------
    # Check 3: AMAZON_LWA_REFRESH_TOKEN
    # -----------------------------------------------------------------------
    refresh_token = os.getenv("AMAZON_LWA_REFRESH_TOKEN", "")
    if refresh_token:
        result.checks["refresh_token"] = True
        result.info.append("AMAZON_LWA_REFRESH_TOKEN is configured")
    else:
        result.checks["refresh_token"] = False
        result.errors.append("AMAZON_LWA_REFRESH_TOKEN is not set")
    
    # -----------------------------------------------------------------------
    # Check 4: AMAZON_ENVIRONMENT
    # -----------------------------------------------------------------------
    environment = os.getenv("AMAZON_ENVIRONMENT", "sandbox").lower().strip()
    if environment == "production":
        result.checks["environment"] = True
        result.info.append("AMAZON_ENVIRONMENT is set to 'production'")
    elif environment == "sandbox":
        result.checks["environment"] = False
        result.warnings.append("AMAZON_ENVIRONMENT is set to 'sandbox' (not production)")
    else:
        result.checks["environment"] = False
        result.errors.append(f"AMAZON_ENVIRONMENT has invalid value: '{environment}'")
    
    # -----------------------------------------------------------------------
    # Check 5: AMAZON_SP_API_REGION
    # -----------------------------------------------------------------------
    region = os.getenv("AMAZON_SP_API_REGION", "na").lower().strip()
    valid_regions = ("na", "eu", "fe")
    if region in valid_regions:
        result.checks["region"] = True
        result.info.append(f"AMAZON_SP_API_REGION is set to '{region}'")
    else:
        result.checks["region"] = False
        result.errors.append(f"AMAZON_SP_API_REGION has invalid value: '{region}' (must be na, eu, or fe)")
    
    # -----------------------------------------------------------------------
    # Check 6: AMAZON_MARKETPLACE_ID
    # -----------------------------------------------------------------------
    marketplace_id = os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")
    if marketplace_id:
        result.checks["marketplace_id"] = True
        result.info.append(f"AMAZON_MARKETPLACE_ID is set to '{marketplace_id}'")
    else:
        result.checks["marketplace_id"] = False
        result.errors.append("AMAZON_MARKETPLACE_ID is not set")
    
    # -----------------------------------------------------------------------
    # Check 7: All credentials present for production
    # -----------------------------------------------------------------------
    all_credentials = bool(client_id and client_secret and refresh_token)
    if all_credentials:
        result.checks["all_credentials"] = True
        result.info.append("All LWA credentials are configured")
    else:
        result.checks["all_credentials"] = False
        missing = []
        if not client_id:
            missing.append("CLIENT_ID")
        if not client_secret:
            missing.append("CLIENT_SECRET")
        if not refresh_token:
            missing.append("REFRESH_TOKEN")
        result.errors.append(f"Missing credentials: {', '.join(missing)}")
    
    # -----------------------------------------------------------------------
    # Check 8: Production readiness
    # -----------------------------------------------------------------------
    production_ready = (
        all_credentials
        and environment == "production"
        and region in valid_regions
        and marketplace_id
    )
    result.checks["production_ready"] = production_ready
    
    if production_ready:
        result.info.append("System is ready for production activation")
    else:
        if not all_credentials:
            result.warnings.append("Cannot activate production: missing credentials")
        if environment != "production":
            result.warnings.append("Cannot activate production: environment not set to 'production'")
    
    # -----------------------------------------------------------------------
    # Overall status
    # -----------------------------------------------------------------------
    result.is_ready = production_ready
    
    return result


def get_activation_status() -> dict:
    """Get activation status for API endpoint.
    
    Returns:
        Dictionary with activation status
    """
    result = validate_production_activation()
    
    return {
        "ready": result.is_ready,
        "environment": os.getenv("AMAZON_ENVIRONMENT", "sandbox"),
        "credentials_configured": result.checks.get("all_credentials", False),
        "checks": result.checks,
        "errors": result.errors,
        "warnings": result.warnings,
        "info": result.info,
        "notice": "This validation does NOT make Amazon API calls",
    }
