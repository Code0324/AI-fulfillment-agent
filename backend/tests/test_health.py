"""Tests for health check endpoints."""

import pytest


def test_root_health(client):
    """GET /health returns 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_health(client):
    """GET /api/v1/health returns 200 with status ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
