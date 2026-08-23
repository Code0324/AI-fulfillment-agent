"""Tests for the GET /api/v1/status endpoint."""

import pytest


def test_api_v1_status_returns_ok(client):
    """GET /api/v1/status returns 200 with exactly {"status": "ok"}."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_status_matches_schema(client):
    """GET /api/v1/status body validates against AppStatus."""
    from app.schemas.status import AppStatus

    response = client.get("/api/v1/status")
    assert response.status_code == 200
    parsed = AppStatus.model_validate(response.json())
    assert parsed.status == "ok"
