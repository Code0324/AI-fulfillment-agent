"""Google Sheets MCP server tests.

No real Google Sheets calls, no network requests, no real credentials —
GOOGLE_SHEETS_CREDENTIALS_PATH is deliberately left unset/invalid in every
test here, exercising the "not configured" path rather than a live API.
"""

import asyncio

import pytest

from mcp_servers.google_sheets import server as sheets_server


@pytest.fixture(autouse=True)
def _unset_credentials(monkeypatch):
    """Every test in this file runs unconfigured — no real credentials file
    exists in the test environment, and none should be required to test
    this server's tool surface and error handling."""
    monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_PATH", raising=False)


def test_lists_expected_tools():
    tools = asyncio.run(sheets_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"read_rows", "append_row", "update_row", "find_row"}


def test_read_rows_reports_not_configured():
    result = sheets_server.read_rows("some-sheet-id", "Sheet1!A1:B2")
    assert result["configured"] is False


def test_append_row_reports_not_configured():
    result = sheets_server.append_row("some-sheet-id", ["a", "b", "c"])
    assert result["configured"] is False


def test_update_row_reports_not_configured():
    result = sheets_server.update_row("some-sheet-id", 5, ["a", "b"])
    assert result["configured"] is False


def test_find_row_reports_not_configured():
    result = sheets_server.find_row("some-sheet-id", "some query")
    assert result["configured"] is False


def test_never_fabricates_success_when_unconfigured():
    """None of the four tools should ever report configured=True or return
    row data when there is no credentials file — that would be exactly the
    kind of fabricated-success this app's other integrations explicitly
    avoid (see app/services/google_sheets/client.py's module docstring)."""
    for result in (
        sheets_server.read_rows("x", "Sheet1!A1:A1"),
        sheets_server.append_row("x", ["v"]),
        sheets_server.update_row("x", 1, ["v"]),
        sheets_server.find_row("x", "q"),
    ):
        assert result["configured"] is False
        assert "rows" not in result
        assert "result" not in result
