"""Google Sheets client for the TikTok order sheet.

Real integration via a service account (gspread + google-auth) — no mock
mode. Writes the exact 15-column business structure the sheet was defined
with (Order ID, Date, SKU, Product Name, Variation, Qty, Recipient, Phone
no, Address 1, Delivery instructions, City, State, Zipcode, Price,
Delivery Date) — nothing invented beyond those columns.

SAFETY:
- Never reports a successful sync unless the Sheets API call actually
  succeeded.
- Never exposes the service account credentials outside this process.
- is_configured is False whenever GOOGLE_SHEETS_SPREADSHEET_ID or
  GOOGLE_SHEETS_CREDENTIALS_JSON is unset — callers must check this before
  calling sync_order() and must not fabricate a "synced" result if it's
  False.
"""

import json
import logging
from datetime import datetime, date

from app.core.config import settings
from app.schemas.tiktok import TikTokOrder

logger = logging.getLogger(__name__)

SHEET_HEADER = [
    "Order ID",
    "Date",
    "SKU",
    "Product Name",
    "Variation",
    "Qty",
    "Recipient",
    "Phone no",
    "Address 1",
    "Delivery instructions",
    "City",
    "State",
    "Zipcode",
    "Price",
    "Delivery Date",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetsError(Exception):
    """Raised when a real Google Sheets operation fails or is not configured."""


def _format_date(value: datetime | date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d")


def _order_to_row(order: TikTokOrder) -> list[str]:
    """Map a TikTokOrder onto the sheet's exact 15 columns, in order."""
    return [
        order.tiktok_order_id,
        _format_date(order.order_date),
        order.sku,
        order.product_name,
        order.variation or "",
        str(order.quantity),
        order.recipient_name,
        order.phone_number,
        order.address_line_1,
        order.delivery_instructions or "",
        order.city,
        order.state,
        order.zipcode,
        f"{order.price:.2f}",
        _format_date(order.delivery_date),
    ]


class GoogleSheetsClient:
    """Thin wrapper over gspread for the TikTok order sheet.

    The underlying gspread client is built lazily on first use (not at
    import time) so importing this module never fails even when
    credentials are absent or malformed — is_configured / connection_status
    report that truthfully instead.
    """

    def __init__(self) -> None:
        self._worksheet = None
        self._init_error: str | None = None
        self._attempted_init = False

    @property
    def is_configured(self) -> bool:
        return settings.is_google_sheets_configured

    def _ensure_worksheet(self):
        if self._worksheet is not None:
            return self._worksheet
        if not self.is_configured:
            raise GoogleSheetsError(
                "Google Sheets is not configured — GOOGLE_SHEETS_SPREADSHEET_ID "
                "and/or GOOGLE_SHEETS_CREDENTIALS_JSON are unset"
            )

        self._attempted_init = True
        try:
            import gspread

            credentials_dict = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS_JSON)
            client = gspread.service_account_from_dict(credentials_dict, scopes=SCOPES)
            spreadsheet = client.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
            worksheet = spreadsheet.worksheet(settings.GOOGLE_SHEETS_WORKSHEET_NAME)
            self._worksheet = worksheet
            self._init_error = None
            return worksheet
        except json.JSONDecodeError as e:
            self._init_error = f"GOOGLE_SHEETS_CREDENTIALS_JSON is not valid JSON: {e}"
            raise GoogleSheetsError(self._init_error) from e
        except Exception as e:
            self._init_error = f"Failed to connect to Google Sheets: {type(e).__name__}: {e}"
            raise GoogleSheetsError(self._init_error) from e

    @property
    def connection_status(self) -> dict:
        """Status for the /sheets/status endpoint. Never fabricates success —
        does not attempt a live connection just to report status (that only
        happens on an actual sync)."""
        if not self.is_configured:
            return {
                "configured": False,
                "notice": "Google Sheets is not configured — GOOGLE_SHEETS_SPREADSHEET_ID / GOOGLE_SHEETS_CREDENTIALS_JSON unset",
            }
        return {
            "configured": True,
            "spreadsheet_id": settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            "worksheet": settings.GOOGLE_SHEETS_WORKSHEET_NAME,
            "connected": self._worksheet is not None,
            "last_error": self._init_error,
            "notice": "Google Sheets credentials configured" + (
                " and a connection has been established" if self._worksheet is not None else " — not yet connected"
            ),
        }

    def test_connection(self) -> dict:
        """Attempt a real connection to the configured spreadsheet/worksheet.

        Unlike connection_status (which only reports whether a connection
        has already been made), this actively tries one — used by the
        dashboard to distinguish NOT_CONFIGURED / CONNECTION_ERROR /
        CONNECTED rather than just "credentials present or not".
        """
        if not self.is_configured:
            return {"success": False, "error": "Google Sheets is not configured"}
        try:
            self._ensure_worksheet()
            return {"success": True}
        except GoogleSheetsError as e:
            return {"success": False, "error": str(e)}

    def sync_order(self, order: TikTokOrder) -> None:
        """Write or update this order's row in the sheet, keyed by Order ID
        (column A). Raises GoogleSheetsError on any failure — callers must
        not treat a missing exception from elsewhere as success.
        """
        worksheet = self._ensure_worksheet()
        row = _order_to_row(order)
        try:
            existing_ids = worksheet.col_values(1)
        except Exception as e:
            raise GoogleSheetsError(f"Failed to read Google Sheet: {type(e).__name__}: {e}") from e

        try:
            row_number = existing_ids.index(order.tiktok_order_id) + 1
            worksheet.update(f"A{row_number}:O{row_number}", [row])
        except ValueError:
            if not existing_ids:
                worksheet.append_row(SHEET_HEADER)
            worksheet.append_row(row)
        except Exception as e:
            raise GoogleSheetsError(f"Failed to write to Google Sheet: {type(e).__name__}: {e}") from e


google_sheets_client = GoogleSheetsClient()
