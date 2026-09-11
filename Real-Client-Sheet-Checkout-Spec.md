# Real Client Sheet Checkout Automation — Spec (CORRECTED)

## Confirmed columns — from client-provided reference image, authoritative, DO NOT
## add/rename/reorder/delete any of these

| Col | Header | Notes |
|---|---|---|
| A | Order ID | Reference/input, given by client |
| B | Date | Reference/input, order date |
| C | SKU | This is the Amazon ASIN directly — product URL is amazon.com/dp/{SKU} |
| D | Product Name | Reference only |
| E | Variation | Product variation if any |
| F | Qty | Quantity to order |
| G | Recipient | Shipping name |
| H | Phone no | Shipping phone |
| I | Address 1 | Street address |
| J | *(blank, no header)* | Leave alone — do not write here unless told to |
| K | Delivery instruct[ions] | If filled, may need to be entered during checkout (e.g. "leave at door") — confirm with real data whether this is used |
| L | City | |
| M | State | |
| N | Zipcode | |
| O | **Price** | SINGLE price column — automation writes the Amazon order total here. No separate "Amazon price" column exists. |
| P | **Delivery Date** | Automation writes the estimated delivery date here |

Correction from earlier draft: there is NO separate "Amazon price" column — only
"Price" (O), and it is the write target for the captured Amazon order total.
"Delivery Date" (P) is the write target for the estimated delivery.

## Confirmed checkout flow (from walkthrough video)

1. Navigate to https://www.amazon.com/dp/{SKU}
2. Add to cart / Buy Now, proceed to checkout
3. Fill shipping address using Recipient / Phone no / Address 1 / City / State /
   Zipcode from the row. If "Delivery instructions" (K) has a value, check if
   Amazon's checkout has a delivery instructions field and fill it there too.
4. A "Choose gift options" page appears:
   - "Gift message" textarea — leave EMPTY (clear it if anything is pre-filled,
     never add a message)
   - "From: [name]" field — Amazon's own pre-filled sender name. DO NOT touch,
     clear, or change this field. Leave it exactly as Amazon shows it.
   - Do NOT check "Wrap it as a gift bag" unless the sheet says to
   - Click "Save gift options" to proceed
5. Reach the final order summary page ("Place Your Order" page,
   amazon.com/checkout/p/.../spc):
   - Confirm delivery address matches the row
   - Capture the "Order total" → write to the "Price" column (O)
   - Capture the estimated delivery date shown → write to "Delivery Date" (P)
6. HARD STOP here — do NOT click "Place your order". Human-approval gate.
7. Highlight/color the row (light green, e.g. #d9ead3) to mark it ready for
   approval — distinct from yellow already used elsewhere in the sheet.

## Claude Code prompt

```
CORRECTION to the column structure — use this exact layout, confirmed from a
client-provided reference image. Do NOT add, rename, reorder, or delete any
column. Columns A-P in order: Order ID, Date, SKU, Product Name, Variation, Qty,
Recipient, Phone no, Address 1, [blank/no header], Delivery instructions, City,
State, Zipcode, Price, Delivery Date.

Important corrections from the earlier spec:
- There is NO separate "Amazon price" column. There is only ONE price column
  ("Price", column O) — this is the write target for the captured Amazon order
  total.
- "Delivery Date" (column P) is the write target for the estimated delivery date.
- Column J has no header — leave it alone, don't write anything there.
- Column K "Delivery instructions" may contain per-order special instructions
  (e.g. "leave at door") — check the real sheet for whether any rows have values
  here, and if Amazon's checkout flow has a delivery-instructions field, fill it
  from this column when present.

Rebuild the "Sheet1" tab's header row on our demo sheet
(1huZFTi7NTzf-evJ63BjuizfovDLUH0ETVJUbJA0Npmg) to match this exact structure, then
add 2 test rows (reuse ASINs B0GJTFXNRX and B0GJTXVN9Z, real US test addresses,
leave Order ID/Date/Price/Delivery Date/Delivery instructions as you see fit for a
test — Order ID can be a simple test ID like TEST-001, Date can be today's date).

Then implement the checkout flow:
1. Navigate to amazon.com/dp/{SKU}, set quantity, add to cart, proceed to
   checkout.
2. Fill shipping address from Recipient/Phone no/Address 1/City/State/Zipcode —
   only once confirmed on a real checkout/address page.
3. If Delivery instructions (K) has a value and Amazon's checkout offers a
   delivery-instructions field, fill it there.
4. Handle "Choose gift options": leave Gift message empty, never touch "From:",
   don't check gift-wrap, click Save gift options.
5. On the order summary page, capture Order total → write to "Price" column, and
   estimated delivery → write to "Delivery Date" column.
6. HARD STOP before "Place your order" — log explicit confirmation this was never
   clicked.
7. Highlight the row light green (#d9ead3) when done.

Also: before running this, check ipinfo.io from Playwright's browser to confirm
we're not still blocked by the Pakistan/amazon.pk routing issue from before —
report this first.

Run against both test rows, report back with screenshots and exactly what was
written to Price and Delivery Date for each.
```
