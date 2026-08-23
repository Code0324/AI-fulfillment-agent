"""Tests for application startup and configuration."""

import pytest

from app.main import app
from app.core.config import settings


def test_app_loads():
    """FastAPI application can be imported and is the correct type."""
    from app.main import app
    from fastapi import FastAPI

    assert isinstance(app, FastAPI)


def test_settings_defaults():
    """Settings load with sensible defaults."""
    assert settings.APP_NAME == "Amazon AI Fulfillment Assistant"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.BACKEND_PORT == 8000
    assert settings.FRONTEND_PORT == 3000


def test_cors_origins_configured():
    """CORS origins include localhost development origins."""
    assert len(settings.CORS_ORIGINS) >= 2
    for origin in settings.CORS_ORIGINS:
        assert "localhost" in origin or "127.0.0.1" in origin


def test_app_metadata(client):
    """FastAPI app exposes correct title and version."""
    assert app.title == settings.APP_NAME
    assert app.version == settings.APP_VERSION
