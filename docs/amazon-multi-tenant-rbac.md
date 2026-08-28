# Multi-Tenant Isolation & RBAC Design

## CHUNK 1T — Amazon LWA Credentials & Authentication Architecture Review

---

## Multi-Tenant Architecture

### Tenant Isolation Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                            │
│                                                                 │
│   Request → Tenant Identification → Tenant Context              │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT A                                    │
│                                                                 │
│   Amazon Connection A                                          │
│   ├── Credentials A (encrypted, isolated)                      │
│   ├── Orders A (isolated)                                      │
│   ├── Fulfillment A (isolated)                                 │
│   └── Audit A (isolated)                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    TENANT B                                    │
│                                                                 │
│   Amazon Connection B                                          │
│   ├── Credentials B (encrypted, isolated)                      │
│   ├── Orders B (isolated)                                      │
│   ├── Fulfillment B (isolated)                                 │
│   └── Audit B (isolated)                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Isolation Rules

| Rule | Description |
|------|-------------|
| Credential Isolation | Tenant A's tokens cannot access Tenant B's Amazon account |
| Data Isolation | Tenant A's orders are invisible to Tenant B |
| Fulfillment Isolation | Tenant A's workflows don't affect Tenant B's inventory |
| Audit Isolation | Tenant A's audit logs don't contain Tenant B's data |
| Network Isolation | Each tenant's Amazon calls use their own tokens |

### Database Relationships

```
Tenant
├── id (primary key)
├── name
├── amazon_connection
│   ├── tenant_id (foreign key)
│   ├── encrypted_refresh_token
│   ├── marketplace_id
│   ├── status (connected/disconnected/needs_reauth)
│   └── last_sync_at
├── orders
│   ├── tenant_id (foreign key)
│   ├── ... (order fields)
├── inventory
│   ├── tenant_id (foreign key)
│   ├── ... (inventory fields)
└── audit_log
    ├── tenant_id (foreign key)
    ├── ... (audit fields)
```

---

## Role-Based Access Control (RBAC)

### Roles

| Role | Description | Amazon Access |
|------|-------------|---------------|
| Admin | Full system access | Connect/disconnect Amazon, manage credentials |
| Manager | Order and fulfillment management | View connection status, trigger imports |
| Operator | Order processing | View orders, start fulfillment |
| Viewer | Read-only access | View orders and status only |

### Permission Matrix

| Action | Admin | Manager | Operator | Viewer |
|--------|-------|---------|----------|--------|
| View Amazon connection status | ✅ | ✅ | ✅ | ✅ |
| Connect Amazon account | ✅ | ❌ | ❌ | ❌ |
| Disconnect Amazon account | ✅ | ❌ | ❌ | ❌ |
| Re-authorize Amazon | ✅ | ✅ | ❌ | ❌ |
| View sync status | ✅ | ✅ | ✅ | ✅ |
| Trigger order import | ✅ | ✅ | ✅ | ❌ |
| View Amazon-related errors | ✅ | ✅ | ✅ | ✅ |
| Manage credentials | ✅ | ❌ | ❌ | ❌ |
| View raw credentials | ✅ | ❌ | ❌ | ❌ |
| View tokens | ❌ | ❌ | ❌ | ❌ |
| View PII | ✅ | ✅ | ❌ | ❌ |

### Access Control Implementation

```python
# Conceptual future implementation

class AmazonPermission(Enum):
    VIEW_CONNECTION_STATUS = "amazon:view_status"
    CONNECT_AMAZON = "amazon:connect"
    DISCONNECT_AMAZON = "amazon:disconnect"
    REAUTHORIZE_AMAZON = "amazon:reauthorize"
    VIEW_SYNC_STATUS = "amazon:view_sync"
    TRIGGER_IMPORT = "amazon:import"
    VIEW_ERRORS = "amazon:view_errors"
    MANAGE_CREDENTIALS = "amazon:manage_credentials"
    VIEW_RAW_CREDENTIALS = "amazon:view_raw_credentials"

ROLE_PERMISSIONS = {
    "admin": [p for p in AmazonPermission],  # All permissions
    "manager": [
        AmazonPermission.VIEW_CONNECTION_STATUS,
        AmazonPermission.VIEW_SYNC_STATUS,
        AmazonPermission.TRIGGER_IMPORT,
        AmazonPermission.VIEW_ERRORS,
        AmazonPermission.REAUTHORIZE_AMAZON,
    ],
    "operator": [
        AmazonPermission.VIEW_CONNECTION_STATUS,
        AmazonPermission.VIEW_SYNC_STATUS,
        AmazonPermission.TRIGGER_IMPORT,
        AmazonPermission.VIEW_ERRORS,
    ],
    "viewer": [
        AmazonPermission.VIEW_CONNECTION_STATUS,
        AmazonPermission.VIEW_SYNC_STATUS,
        AmazonPermission.VIEW_ERRORS,
    ],
}
```

### Least Privilege Principle

1. No ordinary user can retrieve raw credentials
2. No user can view tokens (access or refresh)
3. Operator role cannot manage connections
4. Viewer role cannot trigger imports
5. Admin role is required for credential management

---

## Authorization Checks

### Before Amazon API Call

```
Request to call Amazon API
        │
        ▼
Check: Is tenant authenticated?
        │ (yes)
        ▼
Check: Does tenant have Amazon connection?
        │ (yes)
        ▼
Check: Is connection status "connected"?
        │ (yes)
        ▼
Check: Is access token valid?
        │ (no) → Refresh token
        │ (refresh failed) → Mark as needs_reauth
        │ (refresh succeeded)
        ▼
Check: Does user have permission for this operation?
        │ (yes)
        ▼
Proceed with Amazon API call
```

### Before Fulfillment

```
Order imported from Amazon
        │
        ▼
Check: Is user authorized to start fulfillment?
        │ (yes)
        │
        ▼
Fulfillment workflow starts
        │
        ▼
Approval gate (existing)
        │
        ▼
External submission (if approved)
```
