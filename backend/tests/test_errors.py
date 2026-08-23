"""Tests for centralized error handling."""

import pytest


def test_404_unknown_route(client):
    """Request to an unknown route returns 404."""
    response = client.get("/nonexistent-route")
    assert response.status_code == 404


def test_404_body(client):
    """404 response body contains an error message."""
    response = client.get("/nonexistent-route")
    body = response.json()
    assert "error" in body


def test_method_not_allowed(client):
    """POST to a GET-only endpoint returns 405."""
    response = client.post("/health")
    assert response.status_code == 405
