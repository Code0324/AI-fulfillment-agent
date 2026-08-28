# Amazon Sandbox Capability Matrix

## CHUNK 1U — Official Amazon Sandbox / Developer Environment

Based on official Amazon documentation (developer-docs.amazon.com/sp-api/docs/sp-api-sandbox).

---

## Sandbox Types

| Type | Description | Orders API Support |
|------|-------------|-------------------|
| Static Sandbox | Returns mock responses via pattern matching | ✅ Yes |
| Dynamic Sandbox | Stateful responses based on request parameters | ❌ No (not for Orders API) |
| Sample AI Sandbox | Local tool using AI to generate responses | ✅ Yes |

---

## Sandbox Endpoints

| Region | Endpoint | AWS Region |
|--------|----------|------------|
| North America | `https://sandbox.sellingpartnerapi-na.amazon.com` | us-east-1 |
| Europe | `https://sandbox.sellingpartnerapi-eu.amazon.com` | eu-west-1 |
| Far East | `https://sandbox.sellingpartnerapi-fe.amazon.com` | us-west-2 |

**Local AI Sandbox**: `http://localhost:9001` (requires Node.js 22+ and AWS Bedrock)

---

## Sandbox Capability Matrix

| Capability | Available? | Required? | Environment | Notes |
|------------|------------|-----------|-------------|-------|
| Authentication test | ✅ Yes | Yes | Sandbox | Use LWA credentials |
| Orders API - searchOrders | ✅ Static | Yes | Sandbox | Returns mock orders |
| Orders API - getOrder | ✅ Static | Yes | Sandbox | Returns mock order |
| Orders API - PII access | ⚠️ Requires RDT | Deferred | Production only | RDT from production needed |
| Shipping address | ✅ Yes (in response) | Yes | Sandbox | Part of order response |
| Buyer information | ⚠️ Requires RDT | Deferred | Production only | Restricted data |
| Order items | ✅ Yes | Yes | Sandbox | Included in getOrder |
| Order status | ✅ Yes | Yes | Sandbox | Included in getOrder |
| Order import (read-only) | ✅ Yes | Yes | Sandbox | Read operations only |
| Real seller data | ❌ No | No | Production only | Never in sandbox |
| Fulfillment submission | ❌ No | No | Future | Out of scope for 1U |
| Order modification | ❌ No | No | Never | Out of scope |
| Order cancellation | ❌ No | No | Never | Out of scope |
| Purchase/payment | ❌ No | No | Never | Out of scope |
| Supplier interaction | ❌ No | No | Never | Out of scope |
| Carrier tracking | ❌ No | No | Future | Out of scope |

---

## Sandbox Rate Limits

| Metric | Limit |
|--------|-------|
| Requests per second | 5 |
| Burst | 15 |

**Note**: Sandbox is for functionality testing, NOT scalability testing.

---

## Local AI Sandbox

The local AI sandbox is available on GitHub and requires:

| Requirement | Details |
|-------------|---------|
| Node.js | 22+ |
| npm | Included with Node.js |
| AWS credentials | For Bedrock access (Claude Haiku) |
| Local deployment | `npm install && npm run build && npm run start` |

**Note**: This is optional. The static sandbox is sufficient for our needs.

---

## Key Findings

1. **Orders API has static sandbox** — returns mock responses
2. **Dynamic sandbox not available for Orders** — only static
3. **PII access requires RDT from production** — cannot test PII in sandbox
4. **Sandbox endpoints are regional** — use NA endpoint for US marketplace
5. **Rate limits are strict** — 5 req/s, burst 15
6. **Static sandbox returns predefined responses** — not realistic data
7. **Local AI sandbox available** — but requires AWS Bedrock (additional dependency)
