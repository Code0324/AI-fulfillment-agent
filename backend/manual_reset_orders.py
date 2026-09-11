#!/usr/bin/env python
"""Manually reset orders to Pending by direct cell update."""

import sys
import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ImportError:
    print("Google libraries not installed")
    sys.exit(1)

SHEET_ID = os.getenv("SHEET_ID")
CREDS_FILE = os.path.join(_REPO_ROOT, "backend/credentials/amazon-fulfillment-agent-117e44d6db29.json")

if not SHEET_ID:
    print("SHEET_ID not set")
    sys.exit(1)

if not os.path.exists(CREDS_FILE):
    print(f"Credentials file not found: {CREDS_FILE}")
    # Try to find it
    alt_creds = os.path.join(_BACKEND_DIR, "credentials/amazon-fulfillment-agent-117e44d6db29.json")
    if os.path.exists(alt_creds):
        CREDS_FILE = alt_creds
        print(f"Found at: {CREDS_FILE}")
    else:
        sys.exit(1)

print(f"Using credentials: {CREDS_FILE}")
print(f"Sheet ID: {SHEET_ID}\n")

# Authenticate
creds = Credentials.from_service_account_file(CREDS_FILE)
service = build("sheets", "v4", credentials=creds)

# Update Status column (L) for rows 2 and 3 to "Pending"
# Row 2 = TEST-001, Row 3 = TEST-002
updates = [
    {"range": "Sheet1!L2", "values": [["Pending"]]},  # TEST-001 status
    {"range": "Sheet1!L3", "values": [["Pending"]]},  # TEST-002 status
]

print("Updating Status to 'Pending' for both test orders...")
try:
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"data": updates, "valueInputOption": "USER_ENTERED"}
    ).execute()
    print("✓ Both orders reset to Pending\n")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

# Verify
print("Verifying...")
result = service.spreadsheets().values().get(
    spreadsheetId=SHEET_ID,
    range="Sheet1!A1:M4"
).execute()

rows = result.get("values", [])
for idx, row in enumerate(rows):
    if idx == 0:
        print(f"Header: {row[0]} ... Status={row[11]}")
    elif idx > 0:
        order_id = row[0] if len(row) > 0 else ""
        status = row[11] if len(row) > 11 else ""
        asin = row[12] if len(row) > 12 else ""
        print(f"Row {idx+1}: Order={order_id}, Status={status}, ASIN={asin}")

print("\n✓ Done")
