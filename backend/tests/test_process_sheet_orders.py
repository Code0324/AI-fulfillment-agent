"""End-to-end test for the sheet-to-Amazon processing pipeline.

Mocks Google Sheets and database, verifying:
  - Pending order fetching and parsing
  - Sheet status updates at every stage
  - Full pipeline flow: Pending -> Mapped -> Fulfilling -> Fulfilled/Error
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import UUID, uuid4

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

os.environ["PRICING_PROVIDER"] = "mock"


# ── Sample sheet data ──────────────────────────────────────────────

HEADER = [
    "Order ID", "Buyer Name", "Shipping Address", "City", "State",
    "Zip", "Country", "Phone", "TikTok SKU", "Qty", "Price Paid",
    "Status", "Amazon ASIN/SKU", "Amazon Order ID", "Tracking Number", "Notes",
]

PENDING_ROWS = [
    HEADER,
    ["SHEET-001", "Alice Smith", "123 Main St", "New York", "NY", "10001", "US", "555-0101", "TIKSKU-A", "2", "29.99", "Pending", "", "", "", ""],
    ["SHEET-002", "Bob Jones", "456 Oak Ave", "Los Angeles", "CA", "90001", "US", "555-0202", "TIKSKU-B", "1", "14.99", "Pending", "", "", "", ""],
]


# ── Tests ──────────────────────────────────────────────────────────

def test_fetch_pending_orders():
    """Verify fetch_pending_orders correctly filters Status=Pending rows."""
    from mcp_servers.google_sheets.sheets_client import sheets_client

    with patch.object(sheets_client, 'read_rows', return_value=PENDING_ROWS):
        pending = sheets_client.fetch_pending_orders("test_id")

    assert len(pending) == 2, f"Expected 2 pending, got {len(pending)}"
    assert pending[0]["order_id"] == "SHEET-001"
    assert pending[0]["tiktok_sku"] == "TIKSKU-A"
    assert pending[0]["row_number"] == 2  # 1-indexed, after header
    assert pending[1]["order_id"] == "SHEET-002"
    assert pending[1]["row_number"] == 3
    print("PASS: test_fetch_pending_orders")


def test_update_order_status():
    """Verify update_order_status writes correct columns L-P."""
    from mcp_servers.google_sheets.sheets_client import sheets_client

    mock_service = MagicMock()
    mock_values = MagicMock()
    mock_service.spreadsheets.return_value.values.return_value = mock_values
    mock_values.update.return_value.execute.return_value = {}

    with patch.object(sheets_client, '_ensure_service', return_value=mock_service):
        sheets_client.update_order_status(
            "test_id", 5, "Mapped",
            amazon_asin_sku="B0TEST123",
            amazon_order_id="AMZ-001",
            tracking_number="TRK-001",
            notes="Test note",
        )

    call_args = mock_values.update.call_args
    # Range should be Sheet1!L5:P5
    range_val = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("range", "")
    assert "L5:P5" in range_val, f"Expected range containing L5:P5, got {range_val}"

    # Values: [Status, Amazon ASIN/SKU, Amazon Order ID, Tracking Number, Notes]
    body = call_args[0][2] if len(call_args[0]) > 2 else call_args[1]["body"]
    values = body["values"][0]
    assert values == ["Mapped", "B0TEST123", "AMZ-001", "TRK-001", "Test note"], \
        f"Unexpected values: {values}"
    print("PASS: test_update_order_status")


def test_full_pipeline_dry_run():
    """Test the full processing pipeline with mocked sheets (dry run)."""
    from mcp_servers.google_sheets.sheets_client import sheets_client
    from jobs.process_sheet_orders import process_pending_orders
    from app.schemas.sku_mapping import MappingResult, MappingStatus

    update_calls = []

    def mock_update(sheet_id, row_number, status, **kwargs):
        update_calls.append({"row": row_number, "status": status, **kwargs})
        return {}

    # Mock SKU mapping to return a successful match
    mock_result = MagicMock()
    mock_result.status.value = "matched"
    mock_result.amazon_sku = "AMZ-SKU-001"
    mock_result.asin = "B0TESTASIN"
    mock_result.confidence_score = 1.0

    with patch.object(sheets_client, 'read_rows', return_value=PENDING_ROWS), \
         patch.object(sheets_client, 'update_order_status', side_effect=mock_update), \
         patch.object(type(sheets_client), 'is_configured', new_callable=PropertyMock, return_value=True), \
         patch('jobs.process_sheet_orders.SHEET_ID', 'test_id'), \
         patch('jobs.process_sheet_orders._get_default_organization_id') as mock_org, \
         patch('jobs.process_sheet_orders.sku_mapping_engine.map_sku', return_value=mock_result):
        mock_org.return_value = UUID("00000000-0000-0000-0000-000000000001")
        results = process_pending_orders(dry_run=True)

    assert results["processed"] == 2, f"Expected 2 processed, got {results['processed']}"
    assert results["failed"] == 0, f"Expected 0 failed, got {results['failed']}"

    # Each order should go: Mapped -> Fulfilling -> Fulfilled
    statuses_by_row = {}
    for call in update_calls:
        row = call["row"]
        statuses_by_row.setdefault(row, []).append(call["status"])

    for row, statuses in statuses_by_row.items():
        assert statuses == ["Mapped", "Fulfilling", "Fulfilled"], \
            f"Row {row}: expected [Mapped, Fulfilling, Fulfilled], got {statuses}"

    print("PASS: test_full_pipeline_dry_run")


def test_pricing_failure_sets_error():
    """Test that pricing failure sets Error status with reason."""
    from mcp_servers.google_sheets.sheets_client import sheets_client
    from app.services.providers.mock.mock_pricing import MockPricingProvider
    from app.services.providers.registry import provider_registry
    from jobs.process_sheet_orders import process_pending_orders

    update_calls = []

    mock_pricing = MockPricingProvider()
    mock_pricing.get_price = lambda asin: {"asin": asin, "price": 9999.99, "currency": "USD", "source": "mock"}
    original_provider = provider_registry.get_pricing_provider()

    # Mock SKU mapping to return a successful match
    mock_mapping = MagicMock()
    mock_mapping.status.value = "matched"
    mock_mapping.amazon_sku = "AMZ-SKU-001"
    mock_mapping.asin = "B0TESTASIN"
    mock_mapping.confidence_score = 1.0

    with patch.object(sheets_client, 'read_rows', return_value=PENDING_ROWS), \
         patch.object(sheets_client, 'update_order_status', side_effect=lambda *a, **kw: update_calls.append({"row": a[1], "status": a[2], **kw}) or {}), \
         patch.object(type(sheets_client), 'is_configured', new_callable=PropertyMock, return_value=True), \
         patch('jobs.process_sheet_orders.SHEET_ID', 'test_id'), \
         patch('jobs.process_sheet_orders._get_default_organization_id') as mock_org, \
         patch('jobs.process_sheet_orders.sku_mapping_engine.map_sku', return_value=mock_mapping):
        mock_org.return_value = UUID("00000000-0000-0000-0000-000000000001")
        provider_registry.set_pricing_provider(mock_pricing)
        try:
            results = process_pending_orders(dry_run=True)
        finally:
            provider_registry.set_pricing_provider(original_provider)

    assert results["failed"] == 2, f"Expected 2 failed (both orders over max price), got {results['failed']}"
    assert results["processed"] == 0

    error_calls = [c for c in update_calls if c["status"] == "Error"]
    assert len(error_calls) == 2, f"Expected 2 Error updates, got {len(error_calls)}"
    for c in error_calls:
        assert "Price check failed" in c.get("notes", ""), f"Missing price failure note: {c}"

    print("PASS: test_pricing_failure_sets_error")


def test_sku_mapping_failure_sets_error():
    """Test that unmapped SKU sets Error status."""
    from mcp_servers.google_sheets.sheets_client import sheets_client
    from jobs.process_sheet_orders import process_pending_orders

    update_calls = []

    # Mock SKU mapping to return NOT_FOUND
    mock_mapping_result = MagicMock()
    mock_mapping_result.status.value = "not_found"
    mock_mapping_result.amazon_sku = None
    mock_mapping_result.asin = None
    mock_mapping_result.confidence_score = 0.0
    mock_mapping_result.reason = "No known mapping"

    with patch.object(sheets_client, 'read_rows', return_value=PENDING_ROWS), \
         patch.object(sheets_client, 'update_order_status', side_effect=lambda *a, **kw: update_calls.append({"row": a[1], "status": a[2], **kw}) or {}), \
         patch.object(type(sheets_client), 'is_configured', new_callable=PropertyMock, return_value=True), \
         patch('jobs.process_sheet_orders.SHEET_ID', 'test_id'), \
         patch('jobs.process_sheet_orders._get_default_organization_id') as mock_org, \
         patch('app.services.sku_mapping.engine.sku_mapping_engine.map_sku', return_value=mock_mapping_result):
        mock_org.return_value = UUID("00000000-0000-0000-0000-000000000001")
        results = process_pending_orders(dry_run=True)

    assert results["failed"] == 2, f"Expected 2 failed, got {results['failed']}"
    error_calls = [c for c in update_calls if c["status"] == "Error"]
    assert len(error_calls) == 2
    for c in error_calls:
        assert "SKU mapping failed" in c.get("notes", ""), f"Missing SKU mapping note: {c}"

    print("PASS: test_sku_mapping_failure_sets_error")


def main():
    print("=" * 60)
    print("Sheet-to-Amazon Processing Pipeline Tests")
    print("=" * 60)

    tests = [
        ("Sheet row parsing", test_fetch_pending_orders),
        ("Sheet status updates", test_update_order_status),
        ("Full pipeline (dry run)", test_full_pipeline_dry_run),
        ("Pricing failure -> Error", test_pricing_failure_sets_error),
        ("SKU mapping failure -> Error", test_sku_mapping_failure_sets_error),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
