"""Application configuration loaded from environment variables.

Includes database, JWT auth, and Amazon SP-API settings.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Valid Amazon environments
AMAZON_ENVIRONMENTS = ("sandbox", "production")


class Settings:
    """Centralised, read-only settings for the application."""

    # Application
    APP_NAME: str = "Amazon AI Fulfillment Assistant"
    APP_VERSION: str = "0.2.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Backend
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Frontend
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "3000"))

    # Database (PostgreSQL async)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/amazon_fulfillment",
    )

    # JWT / Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-dev-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    # CORS — localhost defaults for local development, plus any extra
    # origins supplied via ALLOWED_ORIGINS (comma-separated) for deployed
    # frontends, e.g. "https://app.example.com,https://my-app.vercel.app"
    _EXTRA_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")
    CORS_ORIGINS: list[str] = [
        f"http://localhost:{FRONTEND_PORT}",
        f"http://127.0.0.1:{FRONTEND_PORT}",
        *[origin.strip() for origin in _EXTRA_ORIGINS.split(",") if origin.strip()],
    ]

    # -------------------------------------------------------------------
    # Amazon SP-API Configuration
    # -------------------------------------------------------------------
    AMAZON_LWA_CLIENT_ID: str = os.getenv("AMAZON_LWA_CLIENT_ID", "")
    AMAZON_LWA_CLIENT_SECRET: str = os.getenv("AMAZON_LWA_CLIENT_SECRET", "")
    AMAZON_LWA_REFRESH_TOKEN: str = os.getenv("AMAZON_LWA_REFRESH_TOKEN", "")
    AMAZON_SP_API_REGION: str = os.getenv("AMAZON_SP_API_REGION", "na")
    AMAZON_MARKETPLACE_ID: str = os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")
    AMAZON_ENVIRONMENT: str = os.getenv("AMAZON_ENVIRONMENT", "sandbox")

    @property
    def is_amazon_configured(self) -> bool:
        """Check if Amazon credentials are configured."""
        return bool(
            self.AMAZON_LWA_CLIENT_ID
            and self.AMAZON_LWA_CLIENT_SECRET
            and self.AMAZON_LWA_REFRESH_TOKEN
        )

    @property
    def amazon_environment(self) -> str:
        """Amazon environment with validation."""
        env = self.AMAZON_ENVIRONMENT.lower().strip()
        if env not in AMAZON_ENVIRONMENTS:
            logger.warning(
                "Invalid AMAZON_ENVIRONMENT '%s' — defaulting to sandbox",
                self.AMAZON_ENVIRONMENT,
            )
            return "sandbox"
        if env == "production" and not self.is_amazon_configured:
            logger.warning(
                "AMAZON_ENVIRONMENT=production but credentials not configured — "
                "falling back to sandbox"
            )
            return "sandbox"
        return env

    @property
    def is_amazon_production(self) -> bool:
        """Check if Amazon production mode is active."""
        return self.amazon_environment == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    # -------------------------------------------------------------------
    # TikTok Shop Open API Configuration
    #
    # TikTok's real OAuth/signing contract and exact endpoint parameter
    # names are partially unverified — see docs/tiktok-integration.md and
    # the plan this was implemented from for exactly which parts are
    # corroborated against TikTok's own docs vs. blocked pending an
    # approved developer app. This settings block only stores credentials;
    # it does not assert the integration is fully verified.
    # -------------------------------------------------------------------
    TIKTOK_APP_KEY: str = os.getenv("TIKTOK_APP_KEY", "")
    TIKTOK_APP_SECRET: str = os.getenv("TIKTOK_APP_SECRET", "")
    TIKTOK_ACCESS_TOKEN: str = os.getenv("TIKTOK_ACCESS_TOKEN", "")
    TIKTOK_REFRESH_TOKEN: str = os.getenv("TIKTOK_REFRESH_TOKEN", "")
    TIKTOK_SHOP_ID: str = os.getenv("TIKTOK_SHOP_ID", "")
    TIKTOK_ENVIRONMENT: str = os.getenv("TIKTOK_ENVIRONMENT", "sandbox")

    # Suggestion floor for the SKU/variation fuzzy matcher (services/sku_mapping).
    # This is NOT an auto-accept threshold — a fuzzy match is never returned
    # as "matched" regardless of score; below this floor a candidate isn't
    # even surfaced as a suggestion. See services/sku_mapping/engine.py.
    SKU_MAPPING_CONFIDENCE_THRESHOLD: float = float(
        os.getenv("SKU_MAPPING_CONFIDENCE_THRESHOLD", "0.90")
    )

    @property
    def is_tiktok_configured(self) -> bool:
        """Check if TikTok Shop credentials are configured."""
        return bool(
            self.TIKTOK_APP_KEY
            and self.TIKTOK_APP_SECRET
            and self.TIKTOK_ACCESS_TOKEN
        )

    @property
    def tiktok_environment(self) -> str:
        """TikTok Shop environment with validation."""
        env = self.TIKTOK_ENVIRONMENT.lower().strip()
        if env not in ("sandbox", "production"):
            logger.warning(
                "Invalid TIKTOK_ENVIRONMENT '%s' — defaulting to sandbox",
                self.TIKTOK_ENVIRONMENT,
            )
            return "sandbox"
        if env == "production" and not self.is_tiktok_configured:
            logger.warning(
                "TIKTOK_ENVIRONMENT=production but credentials not configured — "
                "falling back to sandbox"
            )
            return "sandbox"
        return env

    @property
    def is_tiktok_production(self) -> bool:
        """Check if TikTok Shop production mode is active."""
        return self.tiktok_environment == "production"

    # -------------------------------------------------------------------
    # Google Sheets Configuration
    #
    # Writes TikTok order rows to a real Google Sheet via a service
    # account. GOOGLE_SHEETS_CREDENTIALS_JSON holds the service account
    # key as a raw JSON string (not a file path) so no credentials file
    # needs to exist on disk — never logged, never exposed to the
    # frontend. See services/google_sheets/client.py.
    # -------------------------------------------------------------------
    GOOGLE_SHEETS_SPREADSHEET_ID: str = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    GOOGLE_SHEETS_CREDENTIALS_JSON: str = os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", "")
    GOOGLE_SHEETS_WORKSHEET_NAME: str = os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME", "Sheet1")

    @property
    def is_google_sheets_configured(self) -> bool:
        """Check if Google Sheets credentials are configured."""
        return bool(self.GOOGLE_SHEETS_SPREADSHEET_ID and self.GOOGLE_SHEETS_CREDENTIALS_JSON)

    # -------------------------------------------------------------------
    # Amazon Pricing Provider Configuration
    #
    # Selects which app.services.providers.pricing_base.PricingProviderBase
    # implementation backs check_price/check_inventory/get_product (both the
    # amazon MCP server and the fulfillment workflow's price safety-gate —
    # see services/fulfillment/workflow.py). Exactly one is active at a
    # time. Defaults to "mock" — see .env.example for the trade-offs of
    # each option; this is a deliberate deploy-time choice, never implied.
    # -------------------------------------------------------------------
    PRICING_PROVIDER: str = os.getenv("PRICING_PROVIDER", "mock")

    # Maximum Amazon price (USD) a fulfillment order is allowed to proceed
    # past automatically. Above this, or if the price can't be determined
    # at all, the workflow stops for human review — see
    # services/fulfillment/workflow.py's _step_check_price_guard.
    MAX_ALLOWED_PRICE_USD: float = float(os.getenv("MAX_ALLOWED_PRICE_USD", "500.00"))

    # Product Advertising API (PA-API v5) — real, live Amazon pricing data.
    # Requires an approved Amazon Associates account; see
    # services/providers/amazon/pa_api_pricing.py's module docstring for the
    # eligibility caveat. AMAZON_PA_API_ENABLED is a separate, explicit gate
    # from merely having credentials set.
    AMAZON_PA_API_ENABLED: bool = os.getenv("AMAZON_PA_API_ENABLED", "false").lower() in ("true", "1", "yes")
    AMAZON_PA_API_ACCESS_KEY: str = os.getenv("AMAZON_PA_API_ACCESS_KEY", "")
    AMAZON_PA_API_SECRET_KEY: str = os.getenv("AMAZON_PA_API_SECRET_KEY", "")
    AMAZON_PA_API_PARTNER_TAG: str = os.getenv("AMAZON_PA_API_PARTNER_TAG", "")
    AMAZON_PA_API_PARTNER_TYPE: str = os.getenv("AMAZON_PA_API_PARTNER_TYPE", "Associates")
    AMAZON_PA_API_MARKETPLACE: str = os.getenv("AMAZON_PA_API_MARKETPLACE", "www.amazon.com")
    AMAZON_PA_API_REGION: str = os.getenv("AMAZON_PA_API_REGION", "us-east-1")
    AMAZON_PA_API_HOST: str = os.getenv("AMAZON_PA_API_HOST", "webservices.amazon.com")

    # Public-product-page scraping fallback — see
    # services/providers/amazon/scrape_pricing.py's module docstring for
    # why this is opt-in and last-resort, not a default.
    AMAZON_SCRAPE_PRICING_ENABLED: bool = os.getenv("AMAZON_SCRAPE_PRICING_ENABLED", "false").lower() in ("true", "1", "yes")

    # -------------------------------------------------------------------
    # Notification Provider Configuration
    #
    # Selects which app.services.providers.notifications_base.
    # NotificationProviderBase implementation backs the notifications MCP
    # server (backend/mcp_servers/notifications/) — used to alert a human
    # about orders sitting in WAITING_APPROVAL or FAILED (price-guard stop,
    # etc.). Defaults to "log" (writes a real log line — never fabricates
    # having reached a human — but doesn't page anyone) so real alerting
    # is a deliberate deploy-time choice, same reasoning as
    # PRICING_PROVIDER above.
    # -------------------------------------------------------------------
    NOTIFICATION_PROVIDER: str = os.getenv("NOTIFICATION_PROVIDER", "log")
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")


settings = Settings()
