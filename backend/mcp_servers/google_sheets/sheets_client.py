"""Generic Google Sheets API v4 client for the MCP server.

PostgreSQL is the source of truth for this application. Everything in this
module is export/sync/reporting only — a spreadsheet read or write here
must never be treated as, or fed back into, authoritative order/inventory
state. See app/services/google_sheets/client.py for the app's actual
source-of-truth-respecting sync path (narrow, single-sheet, TikTok-order
shaped) — this module is intentionally separate and more generic, because
the MCP tools this backs (read_rows/append_row/update_row/find_row) need
to operate on an arbitrary sheet_id/range an agent supplies, not the one
fixed spreadsheet+worksheet that module is wired to.

Uses a service account key FILE (path from GOOGLE_SHEETS_CREDENTIALS_PATH),
unlike app/services/google_sheets/client.py which reads the key as a JSON
string from GOOGLE_SHEETS_CREDENTIALS_JSON — both are supported in this repo
for their respective, separate use cases; nothing here changes that module.
"""

import logging
import os

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClientError(Exception):
    """Raised when a Google Sheets operation fails or is not configured."""


class GenericSheetsClient:
    """Thin wrapper over the Google Sheets API v4 (googleapiclient), built
    lazily so importing this module never fails when credentials are absent.
    """

    def __init__(self) -> None:
        self._service = None

    @property
    def credentials_path(self) -> str:
        return os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "")

    @property
    def is_configured(self) -> bool:
        path = self.credentials_path
        return bool(path) and os.path.isfile(path)

    def _ensure_service(self):
        if self._service is not None:
            return self._service
        if not self.is_configured:
            raise SheetsClientError(
                "Google Sheets is not configured — GOOGLE_SHEETS_CREDENTIALS_PATH "
                "is unset or does not point at a real file"
            )
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            creds = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
            return self._service
        except SheetsClientError:
            raise
        except Exception as e:
            raise SheetsClientError(f"Failed to build Google Sheets client: {type(e).__name__}: {e}") from e

    def read_rows(self, sheet_id: str, range_: str) -> list[list]:
        """Read cell values for an A1 range, e.g. "Sheet1!A1:O50"."""
        service = self._ensure_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range_)
                .execute()
            )
        except Exception as e:
            raise SheetsClientError(f"Failed to read range {range_!r}: {type(e).__name__}: {e}") from e
        return result.get("values", [])

    def append_row(self, sheet_id: str, values: list, sheet_name: str = "Sheet1") -> dict:
        """Append one row of values to the end of a sheet/tab."""
        service = self._ensure_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=sheet_id,
                    range=sheet_name,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": [values]},
                )
                .execute()
            )
        except Exception as e:
            raise SheetsClientError(f"Failed to append row: {type(e).__name__}: {e}") from e
        return result

    def update_row(self, sheet_id: str, row_id: int, values: list, sheet_name: str = "Sheet1") -> dict:
        """Overwrite one 1-indexed row (starting at column A) with `values`."""
        if row_id < 1:
            raise SheetsClientError("row_id must be >= 1")
        end_col = _column_letter(len(values))
        range_ = f"{sheet_name}!A{row_id}:{end_col}{row_id}"
        service = self._ensure_service()
        try:
            result = (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=sheet_id,
                    range=range_,
                    valueInputOption="USER_ENTERED",
                    body={"values": [values]},
                )
                .execute()
            )
        except Exception as e:
            raise SheetsClientError(f"Failed to update row {row_id}: {type(e).__name__}: {e}") from e
        return result

    def find_row(self, sheet_id: str, query: str, sheet_name: str = "Sheet1") -> dict | None:
        """Linear-scan a sheet/tab for the first row containing `query` in
        any cell (case-insensitive substring match). Returns the 1-indexed
        row number and its values, or None if no row matches.
        """
        rows = self.read_rows(sheet_id, sheet_name)
        needle = query.lower()
        for idx, row in enumerate(rows, start=1):
            if any(needle in str(cell).lower() for cell in row):
                return {"row_id": idx, "values": row}
        return None


def _column_letter(n: int) -> str:
    """1 -> 'A', 26 -> 'Z', 27 -> 'AA', ... (n = number of columns)."""
    letters = ""
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters or "A"


sheets_client = GenericSheetsClient()
