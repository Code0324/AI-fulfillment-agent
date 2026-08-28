# Amazon Integration Boundary — Architecture Design

## CHUNK 1R — Official API Readiness & Compliance Design

This document defines the architectural boundary between the existing fulfillment system and a future official Amazon integration.

---

## Guiding Principle

The internal fulfillment workflow must **never** become Amazon-specific. Amazon is one possible data source behind a provider adapter. The system must continue to work with `MockOrderProvider` indefinitely.

---

## Integration Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXTERNAL (Future)                           │
│                                                                 │
│   Amazon SP-API ──→ Amazon Credentials ──→ Amazon Rate Limits   │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [ NETWORK BOUNDARY ]
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  AMAZON PROVIDER ADAPTER                        │
│                                                                 │
│   AmazonOrderProvider(BaseProvider)                             │
│     ├── Authenticates with SP-API                               │
│     ├── Fetches Amazon orders                                   │
│     ├── Transforms Amazon response → Internal OrderCreate       │
│     ├── Redacts PII before returning                            │
│     └── Handles Amazon-specific errors                          │
│                                                                 │
│   Amazon-specific models stay INSIDE this boundary:             │
│     - AmazonOrder, AmazonAddress, AmazonItem                    │
│     - SP-API response types                                     │
│     - Authentication tokens                                     │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [ PROVIDER BOUNDARY ]
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                 EXISTING INTERNAL SYSTEM                        │
│                                                                 │
│   OrderService          ← receives OrderCreate (provider-       │
│   InventoryService          agnostic schema)                    │
│   AddressProcessingService                                       │
│   FulfillmentWorkflowEngine                                      │
│   ApprovalGate                                                   │
│   MockSupplierProvider                                           │
│   MockTrackingProvider                                           │
│                                                                 │
│   NO Amazon-specific code exists here.                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Boundary Rules

1. **Amazon-specific types** (SP-API responses, tokens, ASINs) stay inside the provider adapter.
2. **Internal types** (`Order`, `OrderCreate`, `AddressProcessingResult`) are provider-agnostic.
3. **The fulfillment engine** never calls Amazon APIs directly.
4. **The approval gate** remains authoritative for all external submissions.
5. **PII is redacted** at the provider boundary before entering the internal system.
6. **Credentials** are managed by the provider adapter, never exposed to the workflow.
7. **Rate limits** are handled by the provider adapter, not the workflow.
8. **The dashboard** remains unchanged — it shows internal status only.

---

## Current Provider Hierarchy

```
BaseProvider (abstract)
├── MockOrderProvider          ← CHUNK 1Q
├── MockSupplierProvider       ← CHUNK 1P
├── MockTrackingProvider       ← CHUNK 1P
└── [Future] AmazonOrderProvider
```

## Registry Pattern

The `ProviderRegistry` supports registering multiple providers. A future `AmazonOrderProvider` would be registered alongside (or instead of) `MockOrderProvider`. The fulfillment engine uses `provider_registry.get_order_provider()` — it does not hardcode which provider to use.

---

## What Changes for Amazon Integration

| Component | Change Required |
|-----------|----------------|
| `BaseProvider` | Add capability flags for Amazon-specific operations |
| `ProviderCapabilities` | Add `supports_amazon_order_read`, `supports_amazon_address_read` |
| `ProviderRegistry` | Add `get_amazon_order_provider()` method |
| `MockOrderProvider` | Unchanged |
| `MockAmazonService` | Unchanged |
| `OrderService` | Unchanged |
| `InventoryService` | Unchanged |
| `AddressProcessingService` | Unchanged |
| `FulfillmentWorkflowEngine` | Unchanged |
| **New**: `AmazonOrderProvider` | Implements `BaseProvider` |
| **New**: `AmazonProviderAdapter` | Transforms Amazon → Internal |
| **New**: `AmazonConfig` | Credentials, rate limits, environment |

---

## Key Insight

The existing architecture already supports this boundary:

- `BaseProvider` is the abstract contract
- `ProviderCapabilities` flags what each provider supports
- `ProviderRegistry` allows swapping providers
- The fulfillment engine uses the provider abstraction, not concrete implementations
- PII redaction exists in `app.core.security`

The only work needed is creating the Amazon-specific adapter that implements the existing interface.
