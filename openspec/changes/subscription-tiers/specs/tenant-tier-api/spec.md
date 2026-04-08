# Spec: tenant-tier-api

**Change**: subscription-tiers
**Domain**: tenant-tier-api
**Status**: draft
**Date**: 2026-04-07

---

## Overview

This domain specifies the API surface for subscription tier visibility: a public tiers listing endpoint for pricing pages, and an authenticated tenant-scoped endpoint that returns the current plan with live usage vs. limits. It also specifies the minimal frontend tier card and quota-exceeded handling. Backend returns enriched usage data; the frontend renders it.

---

## Definitions

| Term | Definition |
|------|-----------|
| `TierResponse` | Pydantic schema for a tier (public-facing, no admin-only fields). |
| `TenantTierResponse` | Pydantic schema combining tier limits with current usage for the authenticated tenant. |
| `usage_summary` | Object with one entry per limited resource: `{ resource, limit, current, percentage_used }`. |
| `percentage_used` | `round((current / limit) * 100, 1)` when limit is not None. `null` when unlimited. |
| `near_limit` | Boolean: `true` when `percentage_used >= 80`. Used by frontend to trigger upgrade prompt. |

---

## REQ-TAP-01: GET /api/v1/tiers

**The system MUST expose a public, unauthenticated endpoint `GET /api/v1/tiers`** that lists all active subscription tiers.

**Response shape:**
```json
{
  "tiers": [
    {
      "id": "uuid",
      "name": "Free",
      "slug": "free",
      "monthly_document_limit": 50,
      "max_templates": 5,
      "max_users": 3,
      "bulk_generation_limit": 5,
      "max_template_shares": 5
    },
    { ... },
    { ... }
  ]
}
```

**Rules:**
- Only `is_active = True` tiers are included.
- Ordered: Free → Pro → Enterprise (ascending by `monthly_document_limit NULLS LAST`).
- Fields with `NULL` limits MUST serialize as `null` in JSON (not omitted).
- `is_active`, `created_at`, `updated_at` MUST NOT be included in the response.
- No authentication required — this endpoint is safe for public pricing pages.

---

## REQ-TAP-02: GET /api/v1/tenant/tier

**The system MUST expose `GET /api/v1/tenant/tier`**, accessible to any authenticated user of the tenant (all roles: `user`, `admin`).

**The endpoint MUST return the current tenant's active tier plus a usage summary.**

**Response shape:**
```json
{
  "tier": {
    "id": "uuid",
    "name": "Free",
    "slug": "free",
    "monthly_document_limit": 50,
    "max_templates": 5,
    "max_users": 3,
    "bulk_generation_limit": 5,
    "max_template_shares": 5
  },
  "usage": {
    "documents_this_month": 23,
    "templates_count": 3,
    "users_count": 2,
    "shares_count": 1
  },
  "limits": {
    "documents": {
      "limit": 50,
      "current": 23,
      "percentage_used": 46.0,
      "near_limit": false
    },
    "templates": {
      "limit": 5,
      "current": 3,
      "percentage_used": 60.0,
      "near_limit": false
    },
    "users": {
      "limit": 3,
      "current": 2,
      "percentage_used": 66.7,
      "near_limit": false
    },
    "shares": {
      "limit": 5,
      "current": 1,
      "percentage_used": 20.0,
      "near_limit": false
    }
  },
  "any_near_limit": false
}
```

**Rules for unlimited resources:**
- When a tier limit is `null` (e.g. Enterprise `max_templates`): `limit = null`, `percentage_used = null`, `near_limit = false`.
- `any_near_limit = true` if ANY resource has `near_limit = true`.

**Authentication:** Standard JWT bearer token. `tenant_id` extracted from the token claims — the caller cannot specify a different tenant. No superadmin bypass for this endpoint.

**Performance:** The endpoint MUST execute at most 4 DB queries (one per usage count + one for the tier). Counts MUST NOT be computed by fetching all entities and counting in Python.

---

## REQ-TAP-03: Pydantic Schemas

**The system MUST define the following schemas in `presentation/schemas/tier.py`:**

```python
class TierPublicSchema(BaseModel):
    id: UUID
    name: str
    slug: str
    monthly_document_limit: int | None
    max_templates: int | None
    max_users: int | None
    bulk_generation_limit: int
    max_template_shares: int | None

class TiersListResponse(BaseModel):
    tiers: list[TierPublicSchema]

class ResourceUsage(BaseModel):
    limit: int | None
    current: int
    percentage_used: float | None  # null when unlimited
    near_limit: bool

class UsageSummary(BaseModel):
    documents_this_month: int
    templates_count: int
    users_count: int
    shares_count: int

class TenantTierResponse(BaseModel):
    tier: TierPublicSchema
    usage: UsageSummary
    limits: dict[str, ResourceUsage]
    any_near_limit: bool
```

**All schemas MUST use `model_config = ConfigDict(from_attributes=True)` (Pydantic v2 style).**

---

## REQ-TAP-04: Router Registration

**Tier endpoints MUST be placed in `presentation/api/v1/tiers.py`** and registered in the main API router at prefix `/api/v1`.

**The router for `GET /tenant/tier` MUST be placed in the same file** (not in a separate `tenants.py` unless one already exists), to keep tier-related routes co-located.

---

## REQ-TAP-05: Existing GET /api/v1/usage Enrichment

**The existing `GET /api/v1/usage` response MUST be extended** to include `limit` and `percentage_used` per resource when the tenant's tier is available:

```json
{
  "month": "2026-04",
  "total_documents": 23,
  "limit": 50,
  "percentage_used": 46.0,
  "by_template": [...],
  "by_user": [...]
}
```

`limit` MUST be `null` for unlimited tiers. `percentage_used` MUST be `null` when `limit` is `null`.

This enrichment is OPTIONAL when QuotaService is not wired — the usage endpoint MUST remain functional for backward compatibility.

---

## REQ-TAP-06: Frontend — Tier Info Card

**A tier info card component MUST be added to the dashboard** (location: `frontend/src/features/usage/TierCard.tsx` or equivalent path in the existing feature structure).

**The card MUST display:**
- Plan name (e.g. "Free Plan")
- For each resource with a non-null limit: progress bar with `current / limit` and label.
- Color coding: green when `percentage_used < 60`, yellow when `60 <= percentage_used < 80`, red when `percentage_used >= 80`.
- "Upgrade" button/link for Free-tier tenants that opens a contact/pricing page. Pro and Enterprise tenants do NOT see an upgrade prompt.

**The card MUST fetch from `GET /api/v1/tenant/tier`** using the existing API client pattern in the project.

**The card MUST be data-driven**: it renders only resources where `limit !== null`. Enterprise tenants with all-null limits see a simplified "Enterprise Plan — Unlimited" view.

---

## REQ-TAP-07: Frontend — Quota Exceeded Modal

**A reusable `QuotaExceededModal` component MUST be created** (location: `frontend/src/components/QuotaExceededModal.tsx` or equivalent).

**Trigger:** Any API call that returns HTTP 429 with `error = "quota_exceeded"` in the JSON body MUST display this modal.

**The modal MUST display:**
- Which resource was exhausted (e.g. "Monthly document limit").
- Current usage and limit.
- CTA: "Contact your administrator to upgrade" (link to contact page or admin email).
- Close button.

**Implementation approach:** The API client interceptor (axios interceptor or equivalent) MUST intercept 429 responses with `error = "quota_exceeded"` and emit an event / set global state that triggers the modal. Individual components MUST NOT each handle 429 independently.

---

## REQ-TAP-08: Frontend — Template Upload Indicator

**The template upload UI MUST show `X / Y templates used`** near the upload button/form.

- Data source: `GET /api/v1/tenant/tier` → `limits.templates.current` and `limits.templates.limit`.
- When limit is null (unlimited): show only the count without a denominator (e.g. "12 templates").
- This indicator MUST be refreshed after a successful template upload (invalidate the tier query).

---

## REQ-TAP-09: Frontend — User Management Indicator

**The user management page header MUST show `X / Y users`** (admin view only).

- Data source: `GET /api/v1/tenant/tier` → `limits.users.current` and `limits.users.limit`.
- When limit is null: show count only.
- Refresh after user creation or deletion.

---

## Scenarios

### SC-TAP-01: GET /api/v1/tiers returns all active tiers

```
Given three active tiers (Free, Pro, Enterprise) in the database
When GET /api/v1/tiers is called without authentication
Then the response status is 200
And the body contains 3 tiers
And tiers are ordered Free → Pro → Enterprise
And null limits serialize as JSON null (not absent)
```

### SC-TAP-02: Inactive tier excluded from public listing

```
Given the Pro tier has is_active = False
When GET /api/v1/tiers is called
Then the response body contains 2 tiers: Free and Enterprise
And the Pro tier is absent
```

### SC-TAP-03: GET /api/v1/tenant/tier requires authentication

```
Given no Authorization header is sent
When GET /api/v1/tenant/tier is called
Then the response status is 401
```

### SC-TAP-04: GET /api/v1/tenant/tier returns correct tier and usage

```
Given an authenticated tenant on the Free plan
And the tenant has generated 23 documents this month
And the tenant has 3 templates, 2 users, 1 share
When GET /api/v1/tenant/tier is called
Then the response status is 200
And tier.name = "Free"
And usage.documents_this_month = 23
And limits.documents.limit = 50
And limits.documents.current = 23
And limits.documents.percentage_used = 46.0
And limits.documents.near_limit = false
And any_near_limit = false
```

### SC-TAP-05: near_limit triggers when >= 80%

```
Given an authenticated tenant on the Free plan (monthly_document_limit = 50)
And the tenant has generated 42 documents this month (84%)
When GET /api/v1/tenant/tier is called
Then limits.documents.near_limit = true
And any_near_limit = true
```

### SC-TAP-06: Enterprise tenant shows null limits

```
Given an authenticated tenant on the Enterprise plan (max_templates = NULL)
When GET /api/v1/tenant/tier is called
Then limits.templates.limit = null
And limits.templates.percentage_used = null
And limits.templates.near_limit = false
```

### SC-TAP-07: Tenant cannot access another tenant's tier

```
Given authenticated user from Tenant A
When GET /api/v1/tenant/tier is called (tenant_id from JWT — no override possible)
Then the response always reflects Tenant A's tier
And no query parameter or body field can redirect to Tenant B
```

### SC-TAP-08: Frontend quota exceeded modal appears on 429

```
Given a tenant on the Free plan with 50/50 documents used
When the user attempts to generate a document from the frontend
And the API returns HTTP 429 with error = "quota_exceeded"
Then the QuotaExceededModal is displayed
And it shows resource_type = "documents", limit_value = 50, current_usage = 50
And a "Contact administrator" CTA is visible
```

### SC-TAP-09: Template upload indicator shows correct count

```
Given a tenant on the Free plan with 3 templates
When the template upload page loads
Then the indicator shows "3 / 5 templates used"
And after uploading a fourth template, the indicator updates to "4 / 5 templates used"
```

### SC-TAP-10: GET /api/v1/usage enriched with limit fields

```
Given an authenticated tenant on the Free plan (monthly_document_limit = 50)
And the tenant has generated 23 documents this month
When GET /api/v1/usage is called
Then the response includes limit = 50
And percentage_used = 46.0
```

---

## Test Requirements

| Test ID | Type | Description |
|---------|------|-------------|
| `test_get_tiers_public_returns_active_tiers` | Integration | SC-TAP-01: 3 tiers returned, ordered correctly. |
| `test_get_tiers_excludes_inactive` | Integration | SC-TAP-02: inactive tier absent. |
| `test_get_tenant_tier_requires_auth` | Integration | SC-TAP-03: 401 without token. |
| `test_get_tenant_tier_returns_usage_summary` | Integration | SC-TAP-04: correct usage values. |
| `test_get_tenant_tier_near_limit_flag` | Integration | SC-TAP-05: near_limit triggers at 80%. |
| `test_get_tenant_tier_enterprise_null_limits` | Integration | SC-TAP-06: null limits serialize correctly. |
| `test_get_tenant_tier_isolated_to_jwt_tenant` | Integration | SC-TAP-07: no cross-tenant leakage. |
| `test_usage_response_enriched_with_limit` | Integration | SC-TAP-10: existing /usage endpoint extended. |
| `test_tier_response_schema_null_fields` | Unit | TierPublicSchema serializes None as null in JSON. |
| `test_resource_usage_percentage_computed` | Unit | ResourceUsage.percentage_used computed correctly from limit + current. |
