"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Provide a TestClient for the FastAPI application."""
    return TestClient(app)
