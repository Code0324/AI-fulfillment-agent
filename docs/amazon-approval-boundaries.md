# Approval Boundaries

## CHUNK 1R — Official API Readiness & Compliance Design

The existing approval gate (CHUNK 1O) is authoritative. This document defines which future operations must remain human-approved.

---

## Approval Matrix

| Operation | Auto/Manual | Justification |
|-----------|------------|---------------|
| Read Amazon Orders | **AUTOMATIC** | Read-only, no side effects |
| Import Amazon Orders | **AUTOMATIC** | Local data import, no external changes |
| Check Inventory | **AUTOMATIC** | Read-only check |
| Process Address | **AUTOMATIC/REVIEW** | Auto-process; review if low confidence |
| Reserve Inventory | **AUTOMATIC** | Local reservation, reversible |
| Prepare Supplier Order | **AUTOMATIC** | Local preparation, no external call |
| Verify Supplier Order | **AUTOMATIC** | Local verification |
| **Submit External Order** | **HUMAN APPROVAL REQUIRED** | Irreversible external action |
| **Modify Amazon Order** | **HUMAN APPROVAL REQUIRED** | External modification (if ever justified) |
| **Cancel Amazon Order** | **HUMAN APPROVAL REQUIRED** | External cancellation |
| **Purchase from Supplier** | **HUMAN APPROVAL REQUIRED** | Financial commitment |
| **Confirm Shipment to Amazon** | **HUMAN APPROVAL REQUIRED** | External status update |

---

## Current Approval Gate

The existing `FulfillmentWorkflowEngine` already enforces:

1. Workflow stops at `WAITING_APPROVAL` before supplier submission
2. User must explicitly approve via `approve_workflow()`
3. Approval expires after `APPROVAL_EXPIRY_SECONDS` (1 hour)
4. Rejection cancels the workflow and releases inventory

**This gate must NOT be weakened for Amazon integration.**

---

## Future Approval Requirements

### Initial Read-Only Integration (Phase 1V)

For the initial read-only integration, **no additional approval gates are needed** because:
- Reading Amazon orders is read-only
- No external state is modified
- The existing approval gate handles the fulfillment submission

### Shipment Confirmation (Future Phase)

If `confirmShipment` is implemented:
- **Must require human approval**
- Must verify tracking number is correct
- Must verify shipment actually occurred
- Must log the confirmation event

### Order Cancellation (Out of Scope)

If order cancellation is ever considered:
- **Must require human approval**
- Must verify reason for cancellation
- Must release inventory
- Must log the cancellation event

---

## Approval Gate Design Principle

```
READ operations     → Automatic (safe, reversible)
WRITE operations    → Human approval required (irreversible)
EXTERNAL operations → Human approval required (external side effects)
```

**No operation should bypass the approval gate without explicit justification.**
