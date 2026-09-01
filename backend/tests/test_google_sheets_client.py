"""Tests for the Google Sheets client's find-or-update idempotency logic
(services/google_sheets/client.py).

No real Google credentials exist in this environment, so these tests
exercise sync_order()'s actual branching logic against a small in-memory
fake worksheet (not a call-count mock) — proving the real behavior: a
second sync of the same TikTok Order ID updates the existing row in
place rather than appending a duplicate.
"""

from datetime import datetime, timezone

import pytest

from app.services.google_sheets.client import (
    GoogleSheetsClient,
    GoogleSheetsError,
    SHEET_HEADER,
)
from app.schemas.tiktok import TikTokOrder


class _FakeWorksheet:
    """Minimal in-memory stand-in for a gspread Worksheet — enough to
    exercise sync_order()'s real read-modify-write logic."""

    def __init__(self):
        self.rows: list[list[str]] = []  # rows[0] is the header once appended

    def col_values(self, col_index: int) -> list[str]:
        idx = col_index - 1
        return [row[idx] if idx < len(row) else "" for row in self.rows]

    def update(self, range_str: str, values: list[list[str]]) -> None:
        # range_str looks like "A{row_number}:O{row_number}" — 1-indexed.
        row_number = int(range_str.split(":")[0][1:])
        self.rows[row_number - 1] = values[0]

    def append_row(self, values: list[str]) -> None:
        self.rows.append(values)


def _order(order_id="TT-1001", price=19.99, product_name="Widget") -> TikTokOrder:
    return TikTokOrder(
        tiktok_order_id=order_id,
        order_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        sku="ABC-M",
        product_name=product_name,
        variation="Red/M",
        quantity=1,
        recipient_name="Jane Doe",
        phone_number="555-0100",
        address_line_1="123 Main St",
        delivery_instructions=None,
        city="Springfield",
        state="IL",
        zipcode="62704",
        price=price,
        delivery_date=None,
        order_status="AWAITING_SHIPMENT",
    )


@pytest.fixture
def sheets_client(monkeypatch) -> tuple[GoogleSheetsClient, _FakeWorksheet]:
    client = GoogleSheetsClient()
    fake_ws = _FakeWorksheet()
    monkeypatch.setattr(type(client), "is_configured", property(lambda self: True))
    monkeypatch.setattr(client, "_worksheet", fake_ws)
    return client, fake_ws


class TestSheetSyncIdempotency:
    """Section 8: synchronizing the same TikTok Order ID twice must UPDATE
    the existing row, never append a duplicate."""

    def test_first_sync_creates_header_and_row(self, sheets_client):
        client, ws = sheets_client
        client.sync_order(_order())
        assert ws.rows[0] == SHEET_HEADER
        assert ws.rows[1][0] == "TT-1001"
        assert len(ws.rows) == 2

    def test_second_sync_of_same_order_id_updates_not_appends(self, sheets_client):
        client, ws = sheets_client
        client.sync_order(_order(price=19.99))
        assert len(ws.rows) == 2  # header + 1 data row

        client.sync_order(_order(price=24.99))  # same tiktok_order_id, changed price

        assert len(ws.rows) == 2, "second sync must UPDATE the existing row, not CREATE a new one"
        assert ws.rows[1][0] == "TT-1001"
        assert ws.rows[1][13] == "24.99"  # price column reflects the update

    def test_different_order_id_appends_a_new_row(self, sheets_client):
        client, ws = sheets_client
        client.sync_order(_order(order_id="TT-1001"))
        client.sync_order(_order(order_id="TT-1002"))

        assert len(ws.rows) == 3  # header + 2 distinct orders
        assert ws.rows[1][0] == "TT-1001"
        assert ws.rows[2][0] == "TT-1002"

    def test_three_syncs_two_ids_one_repeat_never_creates_duplicates(self, sheets_client):
        """End-to-end idempotency check matching the exact scenario in the
        brief: CREATE, then CREATE (different id), then UPDATE (repeat of
        the first id) — never CREATE, CREATE, CREATE."""
        client, ws = sheets_client
        client.sync_order(_order(order_id="TT-2001", product_name="Widget A"))
        client.sync_order(_order(order_id="TT-2002", product_name="Widget B"))
        client.sync_order(_order(order_id="TT-2001", product_name="Widget A (updated)"))

        order_ids_in_sheet = [row[0] for row in ws.rows[1:]]
        assert order_ids_in_sheet == ["TT-2001", "TT-2002"]  # no duplicate TT-2001 row
        assert ws.rows[1][3] == "Widget A (updated)"


class TestNotConfiguredNeverFabricatesSuccess:
    def test_sync_raises_when_not_configured(self):
        client = GoogleSheetsClient()
        assert client.is_configured is False
        with pytest.raises(GoogleSheetsError):
            client.sync_order(_order())

    def test_test_connection_reports_failure_when_not_configured(self):
        client = GoogleSheetsClient()
        result = client.test_connection()
        assert result["success"] is False
