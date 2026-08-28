# What Must NOT Be Built — Out of Scope

## CHUNK 1R — Official API Readiness & Compliance Design

This section is **mandatory** and must be reviewed before any future Amazon integration.

---

## Explicitly Out of Scope

| Item | Status | Reason |
|------|--------|--------|
| Amazon scraping | ❌ NEVER | Violates Amazon ToS |
| Seller Central browser automation | ❌ NEVER | Unreliable, violates ToS |
| Cookie/session automation | ❌ NEVER | Security risk |
| CAPTCHA bypass | ❌ NEVER | Illegal in many jurisdictions |
| MFA bypass | ❌ NEVER | Security violation |
| Bot protection bypass | ❌ NEVER | Violates Amazon ToS |
| Credential harvesting | ❌ NEVER | Illegal |
| Unofficial Amazon endpoints | ❌ NEVER | Unreliable, may break |
| Automated purchasing without approval | ❌ NEVER | Financial risk |
| Uncontrolled order modification | ❌ NEVER | Business risk |
| Production Amazon credentials in code | ❌ NEVER | Security violation |
| Production deployment without review | ❌ NEVER | Risk management |
| Real customer data in tests | ❌ NEVER | Privacy violation |
| Amazon API calls in tests | ❌ NEVER | Rate limits, reliability |
| Amazon credentials in Git | ❌ NEVER | Security violation |
| Amazon credentials in logs | ❌ NEVER | Security violation |
| PII in audit logs | ❌ NEVER | Privacy violation |
| Automated order cancellation | ❌ NEVER | Business risk without approval |
| Automated payment processing | ❌ NEVER | Financial risk |
| Amazon marketplace manipulation | ❌ NEVER | Illegal |

---

## Why These Are Out of Scope

1. **Legal**: Many of these violate Amazon's Terms of Service
2. **Reliability**: Browser automation is fragile and breaks frequently
3. **Security**: Credential handling must be controlled and audited
4. **Business**: Automated external actions require human oversight
5. **Compliance**: Amazon has strict policies about automation

---

## What IS In Scope

| Item | Status | Phase |
|------|--------|-------|
| Official SP-API integration | ✅ Planned | 1V |
| Read-only order retrieval | ✅ Planned | 1V |
| Mock data for testing | ✅ Done | 1Q |
| Provider abstraction | ✅ Done | 1P |
| Approval gate | ✅ Done | 1O |
| Audit logging | ✅ Done | 1O |
| PII protection | ✅ Done | 1Q |

---

## Review Required

Before any future Amazon integration:

1. Review Amazon's current Terms of Service
2. Review SP-API acceptable use policy
3. Verify developer account is in good standing
4. Confirm required permissions are approved
5. Test in Amazon sandbox environment first
6. Get explicit user approval for any external actions

---

## Critical Rule

**If in doubt, don't build it.**

When a proposed capability requires:
- Additional Amazon approval
- Restricted permissions
- Special seller authorization
- Another compliance step

**STOP at documentation and clearly flag it.**

The goal is to **UNDERSTAND → DOCUMENT → DESIGN → TEST THE BOUNDARY**, not to **CONNECT → CALL AMAZON → AUTOMATE AMAZON**.
