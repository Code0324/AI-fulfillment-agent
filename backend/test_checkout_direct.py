"""
Direct test: Run checkout against the 2 test ASINs with correct column mapping.

This is a simpler test that doesn't depend on sheet row structure.
"""

from __future__ import annotations

import logging
import os
import sys

# Path setup
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"), override=True)

from app.services.fulfillment.guest_checkout import run_guest_checkout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Test cases: (Order ID, ASIN, Recipient, Address, City, State, Zip, Delivery Instructions)
TEST_CASES = [
    (
        "TEST-001",
        "B0GJTFXNRX",  # Fire TV Stick 4K
        "John Smith",
        "1234 Pike Street",
        "Seattle",
        "WA",
        "98101",
        "",  # No delivery instructions
    ),
    (
        "TEST-002",
        "B0GJTXVN9Z",  # Echo Dot 5th Gen
        "Jane Doe",
        "2345 University Avenue",
        "Seattle",
        "WA",
        "98105",
        "leave at door",  # Delivery instructions
    ),
]

def main():
    logger.info("=" * 72)
    logger.info("DIRECT CHECKOUT TEST - Testing both ASINs")
    logger.info("=" * 72)
    logger.info("IP: Karachi, Pakistan - using built-in location override\n")

    results = []

    for order_id, asin, recipient, address, city, state, zipcode, delivery_instr in TEST_CASES:
        logger.info(f"\n{'=' * 72}")
        logger.info(f"Order: {order_id} (ASIN: {asin})")
        logger.info(f"Recipient: {recipient}")
        logger.info(f"Address: {address}, {city}, {state} {zipcode}")
        logger.info(f"Delivery Instructions: {delivery_instr if delivery_instr else '(none)'}")
        logger.info(f"{'=' * 72}\n")

        try:
            result = run_guest_checkout(
                asin=asin,
                quantity=1,
                buyer_name=recipient,
                shipping_address=address,
                city=city,
                state=state,
                zip_code=zipcode,
                country="US",
                delivery_instructions=delivery_instr,
            )

            logger.info(f"\n✓ CHECKOUT COMPLETED")
            logger.info(f"  Success: {result.success}")
            logger.info(f"  Status: {result.status_to_write}")
            logger.info(f"  Total Price: {result.total_price}")
            logger.info(f"  Estimated Delivery: {result.estimated_delivery}")
            logger.info(f"  Screenshot: {result.screenshot_path}")

            results.append({
                "order_id": order_id,
                "asin": asin,
                "success": result.success,
                "price": result.total_price,
                "delivery": result.estimated_delivery,
                "screenshot": result.screenshot_path,
                "notes": result.notes[:200] if result.notes else "",
            })

        except Exception as e:
            logger.error(f"\n✗ CHECKOUT FAILED: {e}", exc_info=True)
            results.append({
                "order_id": order_id,
                "asin": asin,
                "success": False,
                "error": str(e),
            })

    # Print final report
    logger.info("\n" + "=" * 72)
    logger.info("FINAL RESULTS")
    logger.info("=" * 72)

    for r in results:
        logger.info(f"\nOrder: {r['order_id']} (ASIN: {r['asin']})")
        if r.get("success") is False and "error" in r:
            logger.info(f"  ✗ Status: FAILED")
            logger.info(f"  Error: {r['error'][:200]}")
        else:
            logger.info(f"  ✓ Status: {('SUCCESS' if r.get('success') else 'FAILED')}")
            logger.info(f"  Price: {r.get('price', 'N/A')}")
            logger.info(f"  Delivery: {r.get('delivery', 'N/A')}")
            if r.get('screenshot'):
                logger.info(f"  Screenshot: {r['screenshot']}")

    logger.info("\n" + "=" * 72)
    logger.info(f"Summary: {sum(1 for r in results if r.get('success'))} succeeded, {sum(1 for r in results if not r.get('success'))} failed")
    logger.info("=" * 72)

if __name__ == "__main__":
    main()
