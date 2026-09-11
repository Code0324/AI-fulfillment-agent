"""
Test script: rebuild Sheet1 with correct structure, add test rows, run checkout.

Structure (A-P):
  A: Order ID
  B: Date
  C: SKU
  D: Product Name
  E: Variation
  F: Qty
  G: Recipient
  H: Phone no
  I: Address 1
  J: [blank/no header]
  K: Delivery instructions
  L: City
  M: State
  N: Zipcode
  O: Price (WRITE TARGET)
  P: Delivery Date (WRITE TARGET)

ASINs to test:
  1. B0GJTFXNRX
  2. B0GJTXVN9Z
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Path setup
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"), override=True)

from app.services.fulfillment.guest_checkout import run_guest_checkout
from mcp_servers.google_sheets.sheets_client import sheets_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

SHEET_ID = os.getenv("SHEET_ID")
if not SHEET_ID:
    raise RuntimeError("SHEET_ID environment variable not set")

# New column structure (0-indexed)
COL_ORDER_ID = 0       # A
COL_DATE = 1           # B
COL_SKU = 2            # C
COL_PRODUCT_NAME = 3   # D
COL_VARIATION = 4      # E
COL_QTY = 5            # F
COL_RECIPIENT = 6      # G
COL_PHONE = 7          # H
COL_ADDRESS_1 = 8      # I
# COL_9 = 9             # J (blank, no header)
COL_DELIVERY_INSTRUCTIONS = 10  # K
COL_CITY = 11          # L
COL_STATE = 12         # M
COL_ZIPCODE = 13       # N
COL_PRICE = 14         # O (WRITE TARGET)
COL_DELIVERY_DATE = 15 # P (WRITE TARGET)

HEADER = [
    "Order ID",              # A
    "Date",                  # B
    "SKU",                   # C
    "Product Name",          # D
    "Variation",             # E
    "Qty",                   # F
    "Recipient",             # G
    "Phone no",              # H
    "Address 1",             # I
    "",                      # J (blank)
    "Delivery instructions", # K
    "City",                  # L
    "State",                 # M
    "Zipcode",               # N
    "Price",                 # O
    "Delivery Date",         # P
]

# Test rows (2 rows with real US test addresses)
TEST_ROWS = [
    [
        "TEST-001",                              # Order ID
        datetime.now().strftime("%m/%d/%Y"),     # Date
        "B0GJTFXNRX",                            # SKU
        "Amazon Fire TV Stick 4K",               # Product Name
        "",                                       # Variation
        "1",                                      # Qty
        "John Smith",                            # Recipient
        "206-555-0123",                          # Phone no
        "1234 Pike Street",                      # Address 1
        "",                                       # J (blank)
        "",                                       # Delivery instructions
        "Seattle",                               # City
        "WA",                                    # State
        "98101",                                 # Zipcode
        "",                                       # Price (to be filled)
        "",                                       # Delivery Date (to be filled)
    ],
    [
        "TEST-002",                              # Order ID
        datetime.now().strftime("%m/%d/%Y"),     # Date
        "B0GJTXVN9Z",                            # SKU
        "Amazon Echo Dot (5th Gen)",             # Product Name
        "",                                       # Variation
        "1",                                      # Qty
        "Jane Doe",                              # Recipient
        "425-555-0456",                          # Phone no
        "2345 University Avenue",                # Address 1
        "",                                       # J (blank)
        "leave at door",                         # Delivery instructions
        "Seattle",                               # City
        "WA",                                    # State
        "98105",                                 # Zipcode
        "",                                       # Price (to be filled)
        "",                                       # Delivery Date (to be filled)
    ],
]

def check_ipinfo():
    """Check ipinfo.io from Playwright to confirm location."""
    logger.info("=" * 72)
    logger.info("STEP 1: Checking ipinfo.io from Playwright browser...")
    logger.info("=" * 72)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = ctx.new_page()

            try:
                page.goto("https://ipinfo.io/json", timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                content = page.content()
                logger.info("ipinfo.io response:")
                logger.info(content[:500])  # Log first 500 chars

                # Check if we're getting US IP
                if "country" in content.lower():
                    if "US" in content or "United States" in content:
                        logger.info("✓ IP location appears to be USA - GOOD!")
                        return True
                    elif "PK" in content or "Pakistan" in content:
                        logger.warning("⚠ IP location is Pakistan (Karachi) - routing issue detected!")
                        logger.warning("⚠ BUT: guest_checkout.py has built-in handling via _set_delivery_location_to_us()")
                        logger.warning("⚠ Will proceed with checkout -- it will set Amazon location to Seattle 98101")
                        return True  # Continue anyway -- checkout has mitigation
                    else:
                        logger.info("⚠ Could not determine exact location from response")
                        return True
            finally:
                page.close()
                ctx.close()
                browser.close()
    except Exception as e:
        logger.error(f"Failed to check ipinfo: {e}")
        return False

def rebuild_sheet_header():
    """Rebuild Sheet1 header row with correct structure."""
    logger.info("\n" + "=" * 72)
    logger.info("STEP 2: Rebuilding Sheet1 header row...")
    logger.info("=" * 72)

    try:
        # Update row 1 with new header
        result = sheets_client.update_row(SHEET_ID, 1, HEADER, sheet_name="Sheet1")
        logger.info(f"✓ Header row updated: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to rebuild header: {e}")
        return False

def add_test_rows():
    """Add 2 test rows to the sheet."""
    logger.info("\n" + "=" * 72)
    logger.info("STEP 3: Adding test rows...")
    logger.info("=" * 72)

    try:
        for idx, row in enumerate(TEST_ROWS, start=1):
            result = sheets_client.append_row(SHEET_ID, row, sheet_name="Sheet1")
            logger.info(f"✓ Test row {idx} appended: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to add test rows: {e}")
        return False

def run_checkout_flow():
    """Run the guest checkout flow for both test rows."""
    logger.info("\n" + "=" * 72)
    logger.info("STEP 4: Running guest checkout flow...")
    logger.info("=" * 72)

    # Read back the sheet to get row numbers
    try:
        rows = sheets_client.read_rows(SHEET_ID, "Sheet1!A1:P100")
    except Exception as e:
        logger.error(f"Failed to read sheet: {e}")
        return []

    if len(rows) < 2:
        logger.error("Could not find header in sheet")
        return []

    results = []

    # Find rows with TEST-001 and TEST-002 order IDs
    test_order_ids = ["TEST-001", "TEST-002"]
    for search_order_id in test_order_ids:
        found_row = None
        found_row_idx = None

        for row_idx, row in enumerate(rows[1:], start=2):  # Skip header row
            if not row or len(row) < 1:
                continue
            cell_val = row[COL_ORDER_ID].strip() if COL_ORDER_ID < len(row) else ""
            if cell_val == search_order_id:
                found_row = row
                found_row_idx = row_idx
                break

        if found_row is None:
            logger.warning(f"Test row with order ID {search_order_id} not found in sheet")
            continue

        row = found_row
        row_idx = found_row_idx
        order_id = search_order_id

        asin = (row[COL_SKU].strip() if COL_SKU < len(row) else "")
        recipient = (row[COL_RECIPIENT].strip() if COL_RECIPIENT < len(row) else "")
        phone = (row[COL_PHONE].strip() if COL_PHONE < len(row) else "")
        address_1 = (row[COL_ADDRESS_1].strip() if COL_ADDRESS_1 < len(row) else "")
        city = (row[COL_CITY].strip() if COL_CITY < len(row) else "")
        state = (row[COL_STATE].strip() if COL_STATE < len(row) else "")
        zipcode = (row[COL_ZIPCODE].strip() if COL_ZIPCODE < len(row) else "")
        delivery_instructions = (row[COL_DELIVERY_INSTRUCTIONS].strip() if COL_DELIVERY_INSTRUCTIONS < len(row) else "")
        qty_str = (row[COL_QTY].strip() if COL_QTY < len(row) else "1")

        try:
            qty = int(qty_str)
        except (ValueError, TypeError):
            qty = 1

        logger.info(f"\nProcessing Row {row_idx}: {order_id} (ASIN: {asin})")
        logger.info(f"  Recipient: {recipient}")
        logger.info(f"  Address: {address_1}, {city}, {state} {zipcode}")
        logger.info(f"  Delivery instructions: {delivery_instructions if delivery_instructions else '(none)'}")

        try:
            result = run_guest_checkout(
                asin=asin,
                quantity=qty,
                buyer_name=recipient,
                shipping_address=address_1,
                city=city,
                state=state,
                zip_code=zipcode,
                country="US",
                delivery_instructions=delivery_instructions,
            )

            logger.info(f"\nCheckout result for {order_id}:")
            logger.info(f"  Success: {result.success}")
            logger.info(f"  Status: {result.status_to_write}")
            logger.info(f"  Total Price: {result.total_price}")
            logger.info(f"  Estimated Delivery: {result.estimated_delivery}")
            logger.info(f"  Notes: {result.notes[:200]}")
            logger.info(f"  Screenshot: {result.screenshot_path}")

            # Update the sheet with price and delivery date
            if result.total_price or result.estimated_delivery:
                update_sheet_with_checkout_result(row_idx, result)

            results.append({
                "row": row_idx,
                "order_id": order_id,
                "asin": asin,
                "success": result.success,
                "price": result.total_price,
                "delivery": result.estimated_delivery,
                "screenshot": result.screenshot_path,
            })

        except Exception as e:
            logger.error(f"Checkout failed for {order_id}: {e}")
            results.append({
                "row": row_idx,
                "order_id": order_id,
                "asin": asin,
                "success": False,
                "error": str(e),
            })

        time.sleep(1.5)  # Pause between orders

    return results

def update_sheet_with_checkout_result(row_idx: int, result):
    """Update the sheet row with captured price and delivery date."""
    try:
        # Read the current row
        range_str = f"Sheet1!A{row_idx}:P{row_idx}"
        rows = sheets_client.read_rows(SHEET_ID, range_str)
        if not rows:
            logger.warning(f"Could not read row {row_idx} for update")
            return

        row = rows[0]
        # Ensure row has 16 elements (A-P)
        while len(row) < 16:
            row.append("")

        # Update price (column O, index 14) and delivery date (column P, index 15)
        row[COL_PRICE] = result.total_price or ""
        row[COL_DELIVERY_DATE] = result.estimated_delivery or ""

        # Write back
        sheets_client.update_row(SHEET_ID, row_idx, row, sheet_name="Sheet1")
        logger.info(f"✓ Row {row_idx} updated with price={result.total_price}, delivery={result.estimated_delivery}")
    except Exception as e:
        logger.error(f"Failed to update row {row_idx}: {e}")

def main():
    logger.info("COMPREHENSIVE SHEET CHECKOUT TEST")
    logger.info("Testing the complete workflow with new column structure")

    # Step 1: Check IP location
    if not check_ipinfo():
        logger.error("IP location check failed - we may be blocked")
        return

    # Step 2: Rebuild sheet header
    if not rebuild_sheet_header():
        logger.error("Failed to rebuild sheet header")
        return

    logger.info("✓ Sheet header rebuilt successfully")
    time.sleep(2)

    # Step 3: Add test rows
    if not add_test_rows():
        logger.error("Failed to add test rows")
        return

    logger.info("✓ Test rows added successfully")
    time.sleep(2)

    # Step 4: Run checkout flow
    results = run_checkout_flow()

    # Print summary
    logger.info("\n" + "=" * 72)
    logger.info("FINAL REPORT")
    logger.info("=" * 72)

    for r in results:
        logger.info(f"\nOrder: {r['order_id']} (Row {r['row']}, ASIN: {r['asin']})")
        if r.get('success') is False and 'error' in r:
            logger.info(f"  ✗ Failed: {r['error']}")
        else:
            logger.info(f"  ✓ Success: {r['success']}")
            logger.info(f"    Price written: {r.get('price', 'N/A')}")
            logger.info(f"    Delivery written: {r.get('delivery', 'N/A')}")
            if r.get('screenshot'):
                logger.info(f"    Screenshot: {r['screenshot']}")

    logger.info("\n" + "=" * 72)
    logger.info(f"Processed {len(results)} order(s)")
    logger.info("=" * 72)

if __name__ == "__main__":
    main()
