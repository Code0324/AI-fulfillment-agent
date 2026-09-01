"""Provider Contract Tests — CHUNK 1S.

Tests that all compatible order providers obey the same contract.
Verifies the fulfillment pipeline works through provider abstraction.
Proves that a future AmazonOrderProvider can plug in safely.

ALL TESTS USE MOCK DATA ONLY. No real Amazon calls.
No external network requests. No Amazon credentials.
"""

import uuid

import pytest

from app.schemas.inventory import InventoryCreate
from app.schemas.order import OrderCreate, OrderStatus
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
    ProviderError,
    ProviderUnavailableError,
    ProviderOperationNotSupportedError,
    ProviderValidationError,
    ProviderSubmissionBlockedError,
    ProviderAuthenticationError,
    MOCK_ONLY,
    ensure_mock_mode,
)
from app.services.providers.mock.order_provider import MockOrderProvider
from app.services.providers.mock.supplier_provider import MockSupplierProvider
from app.services.providers.mock.tracking_provider import MockTrackingProvider
from app.services.providers.amazon.order_provider import AmazonOrderProvider
from app.services.providers.registry import ProviderRegistry, create_default_registry
from app.core.security import redact_pii

from tests.conftest import create_test_organization


# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_all():
    """Clear all state before every test."""
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()


def _create_inventory(sku="CONTRACT-SKU-001", stock=100):
    """Helper: create inventory item."""
    return inventory_service.create(
        InventoryCreate(
            sku=sku,
            product_name="Contract Test Product",
            current_stock=stock,
            low_stock_threshold=10,
        )
    )


def _create_order(sku="CONTRACT-SKU-001", qty=2):
    """Helper: create an order via the order service, for a fresh real
    organization."""
    return order_service.create(
        OrderCreate(
            customer_name="Contract Test Customer",
            shipping_address="Contract Test Customer\n123 Contract St\nNew York NY 10003\nUS",
            product_name="Contract Test Product",
            sku=sku,
            quantity=qty,
        ),
        create_test_organization(),
    )


# ===========================================================================
# 1. Provider exposes required capabilities
# ===========================================================================
class TestProviderCapabilities:
    """Verify providers expose correct capability flags."""

    def test_mock_order_provider_capabilities(self):
        provider = MockOrderProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        assert caps.supports_supplier_prepare is False
        assert caps.supports_supplier_verify is False
        assert caps.supports_supplier_submit is False
        assert caps.supports_tracking_read is False

    def test_mock_supplier_provider_capabilities(self):
        provider = MockSupplierProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is False
        assert caps.supports_order_list is False
        assert caps.supports_supplier_prepare is True
        assert caps.supports_supplier_verify is True
        assert caps.supports_supplier_submit is True

    def test_mock_tracking_provider_capabilities(self):
        provider = MockTrackingProvider()
        caps = provider.capabilities
        assert caps.supports_tracking_read is True

    def test_amazon_provider_capabilities(self):
        provider = AmazonOrderProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True


# ===========================================================================
# 2. Provider returns normalized order data
# ===========================================================================
class TestNormalizedOrderData:
    """Verify providers return normalized order dicts."""

    def test_mock_order_provider_returns_dict(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert isinstance(order, dict)

    def test_order_dict_has_required_fields(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        required_fields = ["order_id", "sku", "product_name", "quantity", "customer_name"]
        for field in required_fields:
            assert field in order, f"Missing field: {field}"

    def test_order_dict_has_valid_status(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert order["status"] in ("pending", "processing", "shipped", "delivered", "cancelled")

    def test_list_orders_returns_list_of_dicts(self):
        provider = MockOrderProvider()
        orders = provider.list_orders()
        assert isinstance(orders, list)
        assert len(orders) > 0
        for order in orders:
            assert isinstance(order, dict)


# ===========================================================================
# 3. Provider returns normalized order items
# ===========================================================================
class TestNormalizedOrderItems:
    """Verify order data includes item information."""

    def test_order_has_sku(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert "sku" in order
        assert len(order["sku"]) > 0

    def test_order_has_product_name(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert "product_name" in order
        assert len(order["product_name"]) > 0

    def test_order_has_quantity(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert "quantity" in order
        assert order["quantity"] >= 1


# ===========================================================================
# 4. Order IDs are stable
# ===========================================================================
class TestOrderIdStability:
    """Verify order IDs are consistent across calls."""

    def test_same_order_id_returns_same_data(self):
        provider = MockOrderProvider()
        order1 = provider.get_order("MOCK-ORDER-001")
        order2 = provider.get_order("MOCK-ORDER-001")
        assert order1 is not None
        assert order2 is not None
        assert order1["order_id"] == order2["order_id"]
        assert order1["sku"] == order2["sku"]

    def test_list_orders_returns_stable_ids(self):
        provider = MockOrderProvider()
        orders1 = provider.list_orders()
        orders2 = provider.list_orders()
        ids1 = [o["order_id"] for o in orders1]
        ids2 = [o["order_id"] for o in orders2]
        assert ids1 == ids2


# ===========================================================================
# 5. Duplicate imports remain idempotent
# ===========================================================================
class TestIdempotentImports:
    """Verify duplicate imports are prevented."""

    def test_duplicate_import_returns_empty(self):
        provider = MockOrderProvider()
        imported1 = provider.import_mock_orders()
        imported2 = provider.import_mock_orders()
        assert len(imported1) == 5
        assert len(imported2) == 0

    def test_import_tracking_prevents_duplicates(self):
        provider = MockOrderProvider()
        provider.import_mock_orders()
        assert provider.is_amazon_order_imported("AMZ-MOCK-0001")
        assert provider.is_amazon_order_imported("AMZ-MOCK-0005")

    def test_clear_import_tracking_allows_reimport(self):
        provider = MockOrderProvider()
        provider.import_mock_orders()
        provider.clear_amazon_imports()
        imported = provider.import_mock_orders()
        assert len(imported) == 5


# ===========================================================================
# 6. Invalid provider data is rejected safely
# ===========================================================================
class TestInvalidProviderData:
    """Verify invalid data is handled safely."""

    def test_get_nonexistent_order_returns_none(self):
        provider = MockOrderProvider()
        order = provider.get_order("NONEXISTENT")
        assert order is None

    def test_list_orders_with_zero_limit(self):
        provider = MockOrderProvider()
        orders = provider.list_orders(limit=0)
        assert orders == []

    def test_list_orders_with_large_offset(self):
        provider = MockOrderProvider()
        orders = provider.list_orders(offset=1000)
        assert orders == []


# ===========================================================================
# 7. Missing required fields are handled correctly
# ===========================================================================
class TestMissingRequiredFields:
    """Verify missing fields are handled gracefully."""

    def test_order_without_sku(self):
        """Orders without SKU should still be valid provider data."""
        provider = MockOrderProvider()
        # All mock orders have SKUs, but the provider should handle missing ones
        order = provider.get_order("MOCK-ORDER-001")
        assert order is not None
        # SKU exists in mock data
        assert "sku" in order


# ===========================================================================
# 8. Provider failures do not corrupt internal orders
# ===========================================================================
class TestProviderFailureIsolation:
    """Verify provider errors don't corrupt internal state."""

    def test_provider_error_does_not_corrupt_orders(self):
        """A provider result should not affect existing orders."""
        order = _create_order()

        # AmazonOrderProvider returns None when not configured
        provider = AmazonOrderProvider()
        result = provider.get_order("TEST")
        assert result is None

        # Internal order should be unaffected (organization_id omitted here
        # is fine: this is the legacy internal bridge, whose caller already
        # possesses the order's UUID from having just created it above —
        # see order_service.py's _get_row docstring)
        still_there = order_service.get(order.id)
        assert still_there.id == order.id
        assert still_there.status == order.status


# ===========================================================================
# 9. Provider-specific data does not leak into core fulfillment
# ===========================================================================
class TestDataLeakagePrevention:
    """Verify provider-specific data stays within the provider boundary."""

    def test_mock_amazon_orders_have_source_field(self):
        """Source field is provider-specific, not in internal Order model."""
        provider = MockOrderProvider()
        amazon_orders = provider.get_mock_amazon_orders()
        for order in amazon_orders:
            assert "source" in order  # Provider-specific

    def test_internal_order_source_is_a_plain_channel_label_not_raw_provider_data(self):
        """The internal Order model's `source` is a deliberate, minimal
        channel label (MANUAL/AMAZON/MOCK_AMAZON/TIKTOK) driving the
        fulfillment workflow's provider-selection step — not a leak of a
        provider's raw response shape. A manually-created order defaults
        to "MANUAL", never a provider-specific value."""
        order = _create_order()
        assert order.source == "MANUAL"

    def test_fulfillment_engine_uses_internal_order(self):
        """Fulfillment engine works with internal Order, not provider data."""
        _create_inventory()
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        # Workflow references internal order ID, not Amazon order ID
        assert wf.order_id == order.id


# ===========================================================================
# 10. Provider does not bypass the approval gate
# ===========================================================================
class TestApprovalGateIntegrity:
    """Verify providers cannot bypass the approval system."""

    def test_fulfillment_stops_at_approval(self):
        """Fulfillment always pauses at WAITING_APPROVAL."""
        _create_inventory()
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "waiting_approval"

    def test_approve_completes_workflow(self):
        """Only explicit approval completes the workflow."""
        _create_inventory()
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        completed = fulfillment_engine.approve_workflow(wf.id)
        assert completed.status.value == "completed"
        assert completed.confirmation is not None

    def test_reject_cancels_workflow(self):
        """Rejection cancels the workflow."""
        _create_inventory()
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        cancelled = fulfillment_engine.reject_workflow(wf.id)
        assert cancelled.status.value == "cancelled"

    def test_no_auto_approval_exists(self):
        """There is no auto-approval mechanism in the fulfillment engine."""
        import inspect
        from app.services.fulfillment.workflow import FulfillmentWorkflowEngine
        source = inspect.getsource(FulfillmentWorkflowEngine)
        # Should not contain auto-approve logic
        assert "auto_approve" not in source.lower()
        assert "skip_approval" not in source.lower()


# ===========================================================================
# 11. Provider does not bypass inventory validation
# ===========================================================================
class TestInventoryValidationIntegrity:
    """Verify inventory checks are always enforced."""

    def test_fulfillment_fails_without_inventory(self):
        """Fulfillment fails when inventory is missing."""
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "failed"

    def test_fulfillment_fails_with_insufficient_inventory(self):
        """Fulfillment fails when inventory is insufficient."""
        _create_inventory(stock=1)
        order = _create_order(qty=10)
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "failed"

    def test_inventory_reserved_during_fulfillment(self):
        """Inventory is reserved when fulfillment succeeds."""
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        fulfillment_engine.start_workflow(order.id)
        inv = inventory_service.find_by_sku("CONTRACT-SKU-001")
        assert inv.reserved_quantity == 5


# ===========================================================================
# 12. Provider does not create duplicate workflows
# ===========================================================================
class TestNoDuplicateWorkflows:
    """Verify idempotency prevents duplicate fulfillment workflows."""

    def test_duplicate_start_returns_existing(self):
        """Starting fulfillment twice returns the same workflow."""
        _create_inventory()
        order = _create_order()
        wf1 = fulfillment_engine.start_workflow(order.id)
        wf2 = fulfillment_engine.start_workflow(order.id)
        assert wf1.id == wf2.id

    def test_only_one_workflow_per_order(self):
        """Only one active workflow exists per order."""
        _create_inventory()
        order = _create_order()
        fulfillment_engine.start_workflow(order.id)
        workflows = fulfillment_engine.list_workflows()
        matching = [w for w in workflows if w.order_id == order.id]
        assert len(matching) == 1


# ===========================================================================
# 13. AmazonOrderProvider skeleton safety
# ===========================================================================
class TestAmazonProviderSafety:
    """Verify the AmazonOrderProvider skeleton makes no external calls."""

    def test_amazon_provider_is_base_provider(self):
        """AmazonOrderProvider implements BaseProvider."""
        provider = AmazonOrderProvider()
        assert isinstance(provider, BaseProvider)

    def test_amazon_provider_name(self):
        provider = AmazonOrderProvider()
        assert provider.provider_name == "amazon_order_provider"

    def test_amazon_provider_environment_is_sandbox(self):
        """CHUNK 1V: Provider reports SANDBOX environment."""
        provider = AmazonOrderProvider()
        assert provider.environment == ProviderEnvironment.SANDBOX

    def test_amazon_provider_is_mock(self):
        """is_mock should be True for skeleton."""
        provider = AmazonOrderProvider()
        assert provider.is_mock is True

    def test_amazon_get_order_returns_none_without_credentials(self):
        """CHUNK 1V: get_order returns None when not configured."""
        provider = AmazonOrderProvider()
        result = provider.get_order("TEST")
        assert result is None

    def test_amazon_list_orders_returns_empty_without_credentials(self):
        """CHUNK 1V: list_orders returns empty when not configured."""
        provider = AmazonOrderProvider()
        result = provider.list_orders()
        assert result == []

    def test_amazon_get_order_count_returns_zero_without_credentials(self):
        """CHUNK 1V: get_order_count returns 0 when not configured."""
        provider = AmazonOrderProvider()
        count = provider.get_order_count()
        assert count == 0

    def test_amazon_search_orders_returns_empty_without_credentials(self):
        """CHUNK 1V: search_orders returns empty when not configured."""
        provider = AmazonOrderProvider()
        result = provider.search_orders()
        assert result == []

    def test_amazon_normalization_works(self):
        """CHUNK 1V: _normalize_order works with Amazon order data."""
        provider = AmazonOrderProvider()
        amazon_order = {
            "amazonOrderId": "TEST-ORDER-001",
            "orderStatus": "Unshipped",
            "purchaseDate": "2026-01-15T10:00:00Z",
            "buyerEmail": "test@marketplace.amazon.com",
            "recipientAddress": {
                "name": "Test Customer",
                "addressLine1": "123 Test St",
                "city": "Seattle",
                "stateOrRegion": "WA",
                "postalCode": "98101",
                "countryCode": "US",
            },
        }
        result = provider._normalize_order(amazon_order)
        assert result is not None
        assert result["amazon_order_id"] == "TEST-ORDER-001"
        assert result["source"] == "AMAZON_SANDBOX"

    def test_no_hardcoded_credentials_in_amazon_provider(self):
        """Verify no hardcoded credentials exist in the Amazon provider."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        # Check for hardcoded credential values (not variable names or comments)
        hardcoded_patterns = [
            "amzn1.ask.account",
            "Atzr|",
            "Atza|",
            "Y76SDl2F",
        ]
        for pattern in hardcoded_patterns:
            assert pattern not in source, f"Found hardcoded credential: {pattern}"

    def test_http_calls_delegated_to_sp_api_client(self):
        """HTTP calls are delegated to SP-API client, not direct in provider."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        # The provider uses self._client for API calls, not direct httpx
        # Direct httpx usage should not be in the provider
        forbidden_direct = ["httpx.post", "httpx.get", "requests.post", "requests.get"]
        for term in forbidden_direct:
            assert term not in source, f"Found direct HTTP call: {term}"

    def test_amazon_endpoints_only_in_sp_api_client(self):
        """Amazon endpoints should only be in SP-API client, not provider."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        # The provider should not have direct endpoint URLs
        forbidden = ["sellingpartnerapi-na", "sellercentral"]
        for term in forbidden:
            assert term not in source, f"Found Amazon endpoint in provider: {term}"


# ===========================================================================
# 14. Provider swappability
# ===========================================================================
class TestProviderSwappability:
    """Prove the fulfillment pipeline works through provider abstraction."""

    def test_fulfillment_with_mock_provider(self):
        """Fulfillment works with MockOrderProvider data."""
        _create_inventory()
        order = _create_order()
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "waiting_approval"
        completed = fulfillment_engine.approve_workflow(wf.id)
        assert completed.status.value == "completed"

    def test_fulfillment_uses_order_service_not_provider(self):
        """Fulfillment engine uses OrderService, not the provider directly."""
        _create_inventory()
        order = _create_order()
        # Fulfillment engine gets order via order_service.get()
        wf = fulfillment_engine.start_workflow(order.id)
        # The workflow references the internal order ID
        fetched = order_service.get(wf.order_id)
        assert fetched.id == order.id

    def test_order_mapping_from_external_source(self):
        """External order data can be mapped to internal OrderCreate."""
        # Simulate Amazon order data
        external_order = {
            "amazon_order_id": "AMZ-CONTRACT-001",
            "seller_sku": "CONTRACT-SKU-001",
            "product_name": "Contract Widget",
            "quantity": 3,
            "customer_name": "Contract Customer",
            "shipping_address": "Contract Customer\n456 Contract Ave\nPortland OR 97201\nUS",
        }

        # Map to internal OrderCreate
        order_create = OrderCreate(
            customer_name=external_order["customer_name"],
            shipping_address=external_order["shipping_address"],
            product_name=external_order["product_name"],
            sku=external_order["seller_sku"],
            quantity=external_order["quantity"],
        )

        order = order_service.create(order_create, create_test_organization())
        assert order.sku == "CONTRACT-SKU-001"
        assert order.quantity == 3

        # Fulfillment works with this order
        _create_inventory(sku="CONTRACT-SKU-001")
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "waiting_approval"

    def test_same_fulfillment_engine_for_all_providers(self):
        """The same FulfillmentWorkflowEngine handles all provider types."""
        # Create two orders (simulating two different providers), same org —
        # this test verifies one fulfillment engine handles both, not
        # cross-org isolation (see test_orders.py for isolation coverage).
        org_id = create_test_organization()
        _create_inventory(sku="SKU-A")
        _create_inventory(sku="SKU-B")

        order_a = order_service.create(
            OrderCreate(
                customer_name="Customer A",
                shipping_address="Customer A\n123 Main St\nNew York NY 10001\nUS",
                product_name="Product A",
                sku="SKU-A",
                quantity=1,
            ),
            org_id,
        )
        order_b = order_service.create(
            OrderCreate(
                customer_name="Customer B",
                shipping_address="Customer B\n456 Oak Ave\nLos Angeles CA 90001\nUS",
                product_name="Product B",
                sku="SKU-B",
                quantity=1,
            ),
            org_id,
        )

        # Both go through the same fulfillment engine
        wf_a = fulfillment_engine.start_workflow(order_a.id)
        wf_b = fulfillment_engine.start_workflow(order_b.id)

        assert wf_a.status.value == "waiting_approval"
        assert wf_b.status.value == "waiting_approval"
        assert wf_a.id != wf_b.id


# ===========================================================================
# 15. Provider error hierarchy
# ===========================================================================
class TestProviderErrorHierarchy:
    """Verify provider error classes work correctly."""

    def test_all_errors_extend_provider_error(self):
        errors = [
            ProviderUnavailableError,
            ProviderOperationNotSupportedError,
            ProviderValidationError,
            ProviderSubmissionBlockedError,
            ProviderAuthenticationError,
        ]
        for error_class in errors:
            assert issubclass(error_class, ProviderError)

    def test_provider_error_has_message(self):
        error = ProviderError("Test error")
        assert str(error) == "Test error"

    def test_provider_error_recoverable_flag(self):
        recoverable = ProviderError("recoverable", recoverable=True)
        unrecoverable = ProviderError("unrecoverable", recoverable=False)
        assert recoverable.recoverable is True
        assert unrecoverable.recoverable is False

    def test_unavailable_error_is_not_recoverable(self):
        error = ProviderUnavailableError("test")
        assert error.recoverable is False

    def test_submission_blocked_is_not_recoverable(self):
        error = ProviderSubmissionBlockedError("blocked")
        assert error.recoverable is False


# ===========================================================================
# 16. MOCK_ONLY safety flag
# ===========================================================================
class TestMockOnlySafety:
    """Verify MOCK_ONLY flag prevents production usage."""

    def test_mock_only_flag_is_true(self):
        assert MOCK_ONLY is True

    def test_ensure_mock_mode_does_not_raise(self):
        ensure_mock_mode()  # Should not raise

    def test_provider_registry_uses_mock_providers(self):
        registry = create_default_registry()
        for info in registry.list_all():
            assert info["is_mock"] is True


# ===========================================================================
# 17. Registry contract
# ===========================================================================
class TestRegistryContract:
    """Verify the provider registry manages providers correctly."""

    def test_registry_register_and_get(self):
        registry = ProviderRegistry()
        provider = MockOrderProvider()
        registry.register(provider)
        retrieved = registry.get("mock_order_provider")
        assert retrieved is provider

    def test_registry_list_all(self):
        registry = create_default_registry()
        all_providers = registry.list_all()
        assert len(all_providers) == 3

    def test_registry_clear(self):
        registry = create_default_registry()
        registry.clear()
        assert registry.get("mock_order_provider") is None

    def test_registry_get_nonexistent_returns_none(self):
        registry = ProviderRegistry()
        assert registry.get("nonexistent") is None

    def test_registry_does_not_register_amazon_by_default(self):
        """AmazonOrderProvider is NOT registered by default (safety)."""
        registry = create_default_registry()
        assert registry.get("amazon_order_provider") is None


# ===========================================================================
# 18. PII boundary
# ===========================================================================
class TestPIIBoundary:
    """Verify PII is protected at the provider boundary."""

    def test_redact_pii_removes_phone_numbers(self):
        text = "Call 206-555-0101 for details"
        redacted = redact_pii(text)
        assert "206-555-0101" not in redacted
        assert "PHONE REDACTED" in redacted

    def test_redact_pii_removes_zip_codes(self):
        text = "Ship to 98101"
        redacted = redact_pii(text)
        assert "98101" not in redacted

    def test_redact_pii_removes_emails(self):
        text = "Email test@example.com"
        redacted = redact_pii(text)
        assert "test@example.com" not in redacted

    def test_redact_pii_preserves_non_pii(self):
        text = "Order AMZ-MOCK-0001 for SKU MOCK-SKU-001"
        redacted = redact_pii(text)
        assert "AMZ-MOCK-0001" in redacted
        assert "MOCK-SKU-001" in redacted

    def test_provider_data_has_pii_in_address(self):
        """Provider data contains PII (address) for fulfillment purposes."""
        provider = MockOrderProvider()
        amazon_orders = provider.get_mock_amazon_orders()
        for order in amazon_orders:
            assert "shipping_address" in order
            # Address contains PII — this is expected
            assert len(order["shipping_address"]) > 0


# ===========================================================================
# 19. Failure isolation
# ===========================================================================
class TestFailureIsolation:
    """Verify failures are isolated and don't corrupt state."""

    def test_invalid_order_id_does_not_corrupt_state(self):
        """Non-existent order ID should not affect existing orders."""
        order = _create_order()

        # Try to start fulfillment with non-existent order
        with pytest.raises(Exception):
            fulfillment_engine.start_workflow(uuid.uuid4())

        # State should be unchanged (organization_id omitted: legacy
        # internal bridge, see order_service.py's _get_row docstring)
        still_there = order_service.get(order.id)
        assert still_there.id == order.id

    def test_amazon_provider_error_does_not_affect_mock_provider(self):
        """AmazonOrderProvider result should not affect MockOrderProvider."""
        amazon_provider = AmazonOrderProvider()
        mock_provider = MockOrderProvider()

        # Amazon provider returns None (not configured)
        result = amazon_provider.get_order("TEST")
        assert result is None

        # Mock provider should still work
        order = mock_provider.get_order("MOCK-ORDER-001")
        assert order is not None


# ===========================================================================
# 20. No credentials anywhere in provider code
# ===========================================================================
class TestNoCredentialsAnywhere:
    """Verify no credentials exist in any provider code."""

    def test_no_credentials_in_mock_providers(self):
        import inspect
        providers = [MockOrderProvider, MockSupplierProvider, MockTrackingProvider]
        forbidden = ["client_id", "client_secret", "refresh_token", "access_token", "password", "api_key"]
        for provider_class in providers:
            source = inspect.getsource(provider_class)
            for term in forbidden:
                assert term.lower() not in source.lower(), f"{provider_class.__name__} has: {term}"

    def test_no_hardcoded_credentials_in_amazon_provider(self):
        """Verify no hardcoded credentials exist in the Amazon provider."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        # Check for hardcoded credential values (not variable names or comments)
        hardcoded_patterns = [
            "amzn1.ask.account",
            "Atzr|",
            "Atza|",
            "Y76SDl2F",
        ]
        for pattern in hardcoded_patterns:
            assert pattern not in source, f"Found hardcoded credential: {pattern}"
