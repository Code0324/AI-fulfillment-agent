#!/usr/bin/env python
"""Debug script to inspect the Orders sheet."""

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

print(f"\nTotal rows: {len(rows)}")
print("\nHeader row (row 1):")
print(rows[0])

print("\n" + "="*120)
print("Data rows (showing Order ID, Status, ASIN/SKU):")
print("="*120)
print(f"{'Row':<5} {'Order ID (A)':<20} {'Status (L)':<15} {'ASIN/SKU (M)':<20}")
print("-"*120)

for idx, row in enumerate(rows[1:], start=2):
    order_id = row[0].strip() if len(row) > 0 and row[0] else "(empty)"
    status = row[11].strip() if len(row) > 11 and row[11] else "(empty)"
    asin_sku = row[12].strip() if len(row) > 12 and row[12] else "(empty)"

    if order_id != "(empty)" or status != "(empty)" or asin_sku != "(empty)":
        print(f"{idx:<5} {order_id:<20} {status:<15} {asin_sku:<20}")
