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


settings = Settings()
