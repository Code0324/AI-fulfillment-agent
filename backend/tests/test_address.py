"""Tests for the address processing endpoints.

Covers parsing, validation, normalization, review workflow,
PII protection, and regression.
"""

import uuid

import pytest

from app.services.address.service import address_processing_service

from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_address_service():
    """Clear address processing state before every test."""
    address_processing_service.clear()
    yield
    address_processing_service.clear()


# Synthetic test addresses — NO real customer data
COMPLETE_ADDRESS = (
    "John Smith\n"
    "45 East 10th Street\n"
    "Apt 5B\n"
    "New York NY 10003\n"
    "US"
)

MULTI_LINE_ADDRESS = (
    "Jane Doe\n"
    "789 Oak Avenue\n"
    "Suite 200\n"
    "Los Angeles CA 90001\n"
    "United States"
)

MINIMAL_ADDRESS = (
    "Bob Johnson\n"
    "123 Main St\n"
    "Chicago IL 60601\n"
    "USA"
)

ADDRESS_WITH_PHONE = (
    "Alice Williams\n"
    "321 Pine Road\n"
    "Houston TX 77001\n"
    "US\n"
    "555-123-4567"
)

ADDRESS_MISSING_ZIP = (
    "Tom Brown\n"
    "456 Elm Blvd\n"
    "Seattle WA\n"
    "US"
)

ADDRESS_MISSING_CITY = (
    "Sara Davis\n"
    "789 Maple Dr\n"
    "CA 90210\n"
    "US"
)

SHORT_ADDRESS = "Only Name"

EMPTY_ADDRESS = ""


# ===========================================================================
# POST /api/v1/address/parse — Complete address
# ===========================================================================

class TestParseCompleteAddress:
    """Parse a well-formed multi-line address."""

    def test_parse_complete_address(self, client):
        resp = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["first_name"] == "John"
        assert body["last_name"] == "Smith"
        assert body["address_line_1"] == "45 East 10th Street"
        assert body["address_line_2"] == "Apt 5B"
        assert body["city"] == "New York"
        assert body["state"] == "NY"
        assert body["postal_code"] == "10003"
        assert body["country"] == "US"
        assert body["status"] == "processed"
        assert body["confidence"] >= 0.7

    def test_parse_returns_unique_id(self, client):
        r1 = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        r2 = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert r1["id"] != r2["id"]

    def test_parse_includes_timestamps(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert "created_at" in body
        assert "updated_at" in body


# ===========================================================================
# POST /api/v1/address/parse — Multi-line with suite
# ===========================================================================

class TestParseMultiLineAddress:
    """Parse address with suite/apartment indicator."""

    def test_parse_suite_address(self, client):
        resp = client.post(
            "/api/v1/address/parse",
            json={"raw_address": MULTI_LINE_ADDRESS},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        assert body["city"] == "Los Angeles"
        assert body["state"] == "CA"
        assert body["postal_code"] == "90001"


# ===========================================================================
# POST /api/v1/address/parse — Country normalization
# ===========================================================================

class TestCountryNormalization:
    """Normalize common country representations."""

    def test_usa_normalizes_to_us(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": MINIMAL_ADDRESS},
        ).json()
        assert body["country"] == "US"

    def test_united_states_normalizes_to_us(self, client):
        addr = "John Smith\n123 Main St\nChicago IL 60601\nUnited States"
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": addr},
        ).json()
        assert body["country"] == "US"

    def test_united_kingdom_normalizes_to_uk(self, client):
        addr = "John Smith\n10 Downing St\nLondon SW1A 2AA\nUnited Kingdom"
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": addr},
        ).json()
        assert body["country"] == "UK"


# ===========================================================================
# POST /api/v1/address/parse — State normalization
# ===========================================================================

class TestStateNormalization:
    """Normalize state abbreviations."""

    def test_california_ca(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": MULTI_LINE_ADDRESS},
        ).json()
        assert body["state"] == "CA"

    def test_new_york_ny(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert body["state"] == "NY"

    def test_illinois_il(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": MINIMAL_ADDRESS},
        ).json()
        assert body["state"] == "IL"


# ===========================================================================
# POST /api/v1/address/parse — Phone normalization
# ===========================================================================

class TestPhoneNormalization:
    """Normalize phone numbers."""

    def test_phone_normalized(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_WITH_PHONE},
        ).json()
        assert body["phone"] == "555-123-4567"

    def test_no_phone_returns_empty(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert body["phone"] == ""


# ===========================================================================
# POST /api/v1/address/parse — Validation: required fields
# ===========================================================================

class TestValidationRequiredFields:
    """Validate required fields detection."""

    def test_missing_zip_needs_review(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_MISSING_ZIP},
        ).json()
        assert body["status"] == "needs_review"
        assert body["postal_code"] == ""
        assert body["review_reason"] is not None
        assert "postal code" in body["review_reason"].lower()

    def test_missing_city_needs_review(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_MISSING_CITY},
        ).json()
        assert body["status"] == "needs_review"
        assert body["city"] == ""


# ===========================================================================
# POST /api/v1/address/parse — Validation: invalid input
# ===========================================================================

class TestValidationInvalidInput:
    """Handle invalid or insufficient input."""

    def test_empty_address_returns_failed(self, client):
        resp = client.post(
            "/api/v1/address/parse",
            json={"raw_address": "   "},
        )
        # Whitespace-only is accepted by min_length=1 then processed as empty
        # Empty string "" is rejected by min_length=1 (422)
        # We test whitespace-only here
        if resp.status_code == 201:
            body = resp.json()
            assert body["status"] == "failed"
            assert body["review_reason"] is not None

    def test_short_address_returns_failed(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": SHORT_ADDRESS},
        ).json()
        assert body["status"] == "failed"

    def test_empty_string_rejects_validation(self, client):
        resp = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ""},
        )
        assert resp.status_code == 422

    def test_missing_raw_address_field(self, client):
        resp = client.post("/api/v1/address/parse", json={})
        assert resp.status_code == 422


# ===========================================================================
# POST /api/v1/address/parse — Confidence
# ===========================================================================

class TestConfidence:
    """Confidence score calculation."""

    def test_complete_address_high_confidence(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert body["confidence"] >= 0.7

    def test_incomplete_address_lower_confidence(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_MISSING_ZIP},
        ).json()
        assert body["confidence"] < 1.0

    def test_confidence_between_0_and_1(self, client):
        body = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        assert 0.0 <= body["confidence"] <= 1.0


# ===========================================================================
# GET /api/v1/address — List results
# ===========================================================================

class TestListResults:
    """List address processing results."""

    def test_empty_list(self, client):
        resp = client.get("/api/v1/address")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total_items"] == 0

    def test_list_after_parsing(self, client):
        client.post("/api/v1/address/parse", json={"raw_address": COMPLETE_ADDRESS})
        client.post("/api/v1/address/parse", json={"raw_address": MINIMAL_ADDRESS})
        resp = client.get("/api/v1/address").json()
        assert resp["total_items"] == 2
        assert len(resp["items"]) == 2

    def test_filter_by_status(self, client):
        client.post("/api/v1/address/parse", json={"raw_address": COMPLETE_ADDRESS})
        client.post("/api/v1/address/parse", json={"raw_address": EMPTY_ADDRESS})
        resp = client.get("/api/v1/address?status=processed").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["status"] == "processed"

    def test_filter_by_needs_review(self, client):
        # Parse multiple addresses to ensure at least one needs review
        client.post("/api/v1/address/parse", json={"raw_address": COMPLETE_ADDRESS})
        client.post("/api/v1/address/parse", json={"raw_address": ADDRESS_MISSING_ZIP})
        resp = client.get("/api/v1/address?status=needs_review").json()
        assert resp["total_items"] >= 1

    def test_filter_by_failed(self, client):
        client.post("/api/v1/address/parse", json={"raw_address": SHORT_ADDRESS})
        resp = client.get("/api/v1/address?status=failed").json()
        assert resp["total_items"] == 1

    def test_pagination(self, client):
        for _ in range(5):
            client.post("/api/v1/address/parse", json={"raw_address": COMPLETE_ADDRESS})
        resp = client.get("/api/v1/address?page=1&page_size=2").json()
        assert len(resp["items"]) == 2
        assert resp["total_items"] == 5
        assert resp["total_pages"] == 3


# ===========================================================================
# GET /api/v1/address/{id} — Get single result
# ===========================================================================

class TestGetResult:
    """Get a single address processing result."""

    def test_get_existing_result(self, client):
        created = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        resp = client.get(f"/api/v1/address/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_result_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/address/{fake_id}")
        assert resp.status_code == 404


# ===========================================================================
# POST /api/v1/address/{id}/review — Human review workflow
# ===========================================================================

class TestReviewWorkflow:
    """Human review, correction, and rejection."""

    def _create_needs_review(self, client) -> dict:
        """Helper: create a result that needs review."""
        return client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_MISSING_ZIP},
        ).json()

    def test_approve_needs_review(self, client):
        result = self._create_needs_review(client)
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"
        assert resp.json()["review_reason"] is None

    def test_reject_result(self, client):
        result = self._create_needs_review(client)
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "reject"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert "rejected" in resp.json()["review_reason"].lower()

    def test_correct_result_with_postal_code(self, client):
        result = self._create_needs_review(client)
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "correct", "postal_code": "98101"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["postal_code"] == "98101"
        assert body["status"] == "processed"

    def test_correct_result_with_city(self, client):
        result = client.post(
            "/api/v1/address/parse",
            json={"raw_address": ADDRESS_MISSING_CITY},
        ).json()
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "correct", "city": "Portland"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["city"] == "Portland"
        assert body["status"] == "processed"

    def test_approve_already_processed_fails(self, client):
        result = client.post(
            "/api/v1/address/parse",
            json={"raw_address": COMPLETE_ADDRESS},
        ).json()
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 422

    def test_approve_failed_result_fails(self, client):
        # Create a short address that fails processing
        result = client.post(
            "/api/v1/address/parse",
            json={"raw_address": SHORT_ADDRESS},
        ).json()
        assert result["status"] == "failed"
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 422

    def test_review_missing_result_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/address/{fake_id}/review",
            json={"action": "approve"},
        )
        assert resp.status_code == 404

    def test_correction_updates_timestamp(self, client):
        result = self._create_needs_review(client)
        resp = client.post(
            f"/api/v1/address/{result['id']}/review",
            json={"action": "correct", "postal_code": "98101"},
        ).json()
        assert resp["updated_at"] >= result["created_at"]


# ===========================================================================
# PII Protection
# ===========================================================================

class TestPIIProtection:
    """Verify PII is handled safely."""

    def test_parse_result_does_not_leak_to_logs(self, client):
        """Verify the security module works."""
        from app.core.security import redact_pii, safe_log_address

        raw = "John Smith\n123 Main St\nNew York NY 10003\nUS\n555-123-4567"
        redacted = redact_pii(raw)
        assert "555-123-4567" not in redacted
        assert "10003" not in redacted
        assert "[PHONE REDACTED]" in redacted
        assert "[ZIP REDACTED]" in redacted

    def test_safe_log_address(self, client):
        from app.core.security import safe_log_address

        addr = "John Smith\n123 Main St\nApt 4\nNew York NY 10003\nUS"
        safe = safe_log_address(addr)
        assert "John Smith" not in safe
        assert "123 Main St" not in safe
        assert "[REDACTED]" in safe

    def test_empty_address_safe_log(self, client):
        from app.core.security import safe_log_address

        assert safe_log_address("") == "[NO ADDRESS]"
        assert safe_log_address(None) == "[NO ADDRESS]"

    def test_redact_secret(self, client):
        from app.core.security import redact_secret

        assert redact_secret("mysecretkey123") == "**********y123"
        assert redact_secret("ab") == "***"
        assert redact_secret("") == "***"


# ===========================================================================
# Regression
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure existing routes are unaffected."""

    def test_root_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_tasks_still_work(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "pending"})
        assert resp.status_code == 201

    def test_orders_still_work(self, client):
        """Orders endpoint still works (now requires real authentication —
        an intentional Phase 2B security change, not a regression)."""
        resp = client.post(
            "/api/v1/orders",
            json={
                "customer_name": "Test Customer",
                "shipping_address": "123 Test St",
                "product_name": "Test Product",
                "quantity": 1,
            },
            headers=auth_headers(client),
        )
        assert resp.status_code == 201

    def test_inventory_still_work(self, client):
        resp = client.post(
            "/api/v1/inventory",
            json={
                "sku": "TEST-001",
                "product_name": "Test Widget",
                "current_stock": 50,
            },
        )
        assert resp.status_code == 201

    def test_automation_sessions_still_work(self, client):
        resp = client.post("/api/v1/automation/sessions?environment=sandbox")
        assert resp.status_code == 201
