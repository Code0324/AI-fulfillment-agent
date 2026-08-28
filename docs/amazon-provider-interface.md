# Amazon Provider Interface — Future Design

## CHUNK 1R — Official API Readiness & Compliance Design

Defines the interface/contract for a future `AmazonOrderProvider` without implementing it.

---

## Design Principle

The interface should support **only the minimum operations justified** by the research. No speculative APIs.

---

## Proposed Interface

```python
class AmazonOrderProvider(BaseProvider):
    """Future Amazon order provider using official SP-API.
    
    Implements the existing BaseProvider interface.
    Amazon-specific logic stays INSIDE this class.
    """
    
    @property
    def provider_name(self) -> str:
        return "amazon_order_provider"
    
    @property
    def environment(self) -> ProviderEnvironment:
        # Returns SANDBOX or PRODUCTION based on config
        ...
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_order_read=True,
            supports_order_list=True,
            # All other capabilities False — read-only
        )
    
    # ---- Read-only operations ----
    
    def search_orders(
        self,
        *,
        created_after: str | None = None,
        created_before: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search Amazon orders by criteria.
        
        Returns list of Amazon order dicts.
        PII is NOT included in returned data.
        """
        ...
    
    def get_order(self, amazon_order_id: str) -> dict | None:
        """Retrieve a single Amazon order by ID.
        
        Returns order dict WITHOUT PII.
        Raises ProviderError on API failure.
        """
        ...
    
    def get_order_items(self, amazon_order_id: str) -> list[dict]:
        """Retrieve order items for a specific order.
        
        Returns list of item dicts.
        """
        ...
    
    # ---- Internal mapping ----
    
    def to_internal_order(self, amazon_order: dict) -> OrderCreate:
        """Transform Amazon order response to internal OrderCreate.
        
        This is the KEY transformation:
        Amazon API Response → Internal OrderCreate
        
        Amazon-specific fields are stripped here.
        PII is redacted here.
        """
        ...
```

---

## Interface Constraints

1. **No write operations** — the provider is read-only
2. **No PII in return values** — PII is stripped/redacted at the boundary
3. **No Amazon-specific types exposed** — returns `dict` or internal types
4. **All errors use existing ProviderError hierarchy** — no new error types
5. **Rate limiting handled internally** — callers see simple request/response
6. **Credential management internal** — callers never see tokens

---

## What NOT to Include in the Interface

| Excluded | Reason |
|----------|--------|
| `confirm_shipment()` | Not needed for initial integration |
| `cancel_order()` | Out of scope — never auto-cancel |
| `modify_order()` | Out of scope |
| `get_buyer_info()` | PII-heavy, not needed |
| `get_order_analytics()` | Not needed |
| `manage_listings()` | Completely out of scope |
| `manage_inventory()` | Out of scope |
| `manage_pricing()` | Out of scope |

---

## Mock Contract Tests

The interface should be testable with mock data:

```python
def test_amazon_provider_implements_base_provider():
    """Verify AmazonOrderProvider can be used like MockOrderProvider."""
    provider = AmazonOrderProvider(...)
    assert isinstance(provider, BaseProvider)
    assert provider.provider_name == "amazon_order_provider"

def test_amazon_provider_transforms_to_internal_order():
    """Verify Amazon response can be transformed to internal OrderCreate."""
    mock_amazon_response = {...}  # Synthetic Amazon response
    order_create = provider.to_internal_order(mock_amazon_response)
    assert isinstance(order_create, OrderCreate)
    assert order_create.sku  # SKU must be mapped
    assert order_create.quantity >= 1

def test_amazon_provider_strips_pii():
    """Verify PII is not returned from provider."""
    mock_amazon_response = {
        "amazon_order_id": "TEST-001",
        "buyer_info": {"name": "Test", "email": "test@example.com"},
        ...
    }
    result = provider.get_order("TEST-001")
    # PII should not be in the result
```

---

## Registry Integration

A future Amazon provider would be registered:

```python
# In ProviderRegistry
def get_order_provider(self) -> BaseProvider:
    """Get the active order provider.
    
    Returns AmazonOrderProvider if configured,
    otherwise falls back to MockOrderProvider.
    """
    # Priority: Amazon (if configured) → Mock
    ...
```

This allows seamless switching between mock and real providers.
