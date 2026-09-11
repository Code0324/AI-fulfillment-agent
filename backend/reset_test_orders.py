#!/usr/bin/env python
"""Reset TEST-001 and TEST-002 to Pending status."""

import sys
import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

from mcp_servers.google_sheets.sheets_client import sheets_client

SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    print("SHEET_ID not set in .env")
    sys.exit(1)

if not sheets_client.is_configured:
    print("Google Sheets not configured")
    sys.exit(1)

print(f"Reading sheet {SHEET_ID}...")
rows = sheets_client.read_rows(SHEET_ID, "Sheet1!A1:P200")

if not rows:
    print("Sheet is empty")
    sys.exit(0)

print(f"\nFound {len(rows)} rows total")

# Find TEST-001 and TEST-002 rows
test_001_row = None
test_002_row = None

for idx, row in enumerate(rows[1:], start=2):  # 1-indexed, skip header
    order_id = row[0].strip() if len(row) > 0 and row[0] else ""
    if order_id == "TEST-001":
        test_001_row = idx
    elif order_id == "TEST-002":
        test_002_row = idx

print(f"\nTEST-001 row number: {test_001_row}")
print(f"TEST-002 row number: {test_002_row}")

if not test_001_row or not test_002_row:
    print("ERROR: Could not find TEST-001 or TEST-002 in sheet")
    sys.exit(1)

# Reset both to "Pending"
print(f"\nResetting TEST-001 (row {test_001_row}) to 'Pending'...")
try:
    sheets_client.update_order_status(SHEET_ID, test_001_row, "Pending", amazon_asin_sku="B0GJTFXNRX")
    print("  ✓ Updated")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

print(f"\nResetting TEST-002 (row {test_002_row}) to 'Pending'...")
try:
    sheets_client.update_order_status(SHEET_ID, test_002_row, "Pending", amazon_asin_sku="B0GJTXVN9Z")
    print("  ✓ Updated")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

print("\n✓ Both orders reset to Pending status")
