"""Application configuration loaded from environment variables."""

import os


class Settings:
    """Centralised, read-only settings for the application."""

    # Application
    APP_NAME: str = "Amazon AI Fulfillment Assistant"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # Backend
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Frontend
    FRONTEND_PORT: int = int(os.getenv("FRONTEND_PORT", "3000"))

    # CORS — allowed origins for local development
    CORS_ORIGINS: list[str] = [
        f"http://localhost:{FRONTEND_PORT}",
        f"http://127.0.0.1:{FRONTEND_PORT}",
    ]

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
