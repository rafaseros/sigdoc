# Proposal: subscription-tiers

## Intent

Introduce a subscription tier system to SigDoc where each **tenant** is assigned a plan (Free, Pro, Enterprise) that governs resource limits: monthly document generation quota, maximum templates, maximum users, bulk generation cap, and template share slots. Usage tracking already records every generation event -- this change adds the enforcement layer that checks tier limits before allowing operations, and provides visibility into usage vs. quota across the UI.

## Problem Statement

Today SigDoc tracks usage but does not enforce any limits based on a subscription plan:

- **No monetization lever**: Every tenant has unlimited document generation. There is no mechanism to differentiate between a free-trial tenant and an enterprise customer.
- **No resource governance**: A single tenant can upload unlimited templates, invite unlimited users, and share templates without bounds. Nothing prevents a free tenant from consuming disproportionate resources.
- **Per-user bulk_generation_limit is a workaround**: The field on User was added as a stopgap. It controls only the bulk Excel row cap, has no concept of monthly quotas, and must be manually set per user by an admin.
- **No upgrade path**: The frontend cannot show "you are on the Free plan, upgrade to Pro" because no plan concept exists.

Without subscription tiers, SigDoc cannot operate as a SaaS product -- it is just a multi-tenant app with no commercial differentiation.

## Scope

### In Scope

1. **Subscription Tier Model (DB table, not hardcoded)**
   - `subscription_tiers` table with columns: `id`, `name`, `slug`, `monthly_document_limit`, `max_templates`, `max_users`, `bulk_generation_limit`, `max_template_shares`, `is_active`, `created_at`, `updated_at`
   - Domain entity `SubscriptionTier` dataclass
   - `SubscriptionTierRepository` port + SQLAlchemy adapter (CRUD + get_by_slug)
   - Seed migration creates three default tiers: Free (50 docs/mo, 5 templates, 3 users, 5 bulk, 5 shares), Pro (500 docs/mo, 50 templates, 20 users, 25 bulk, 50 shares), Enterprise (5000 docs/mo, unlimited templates, unlimited users, 100 bulk, unlimited shares)

2. **Tenant-Tier Association**
   - Add `tier_id` (FK to subscription_tiers, NOT NULL, default Free) to `tenants` table
   - Update `Tenant` domain entity and `TenantModel` ORM model
   - Existing tenants migrate to the Free tier (the seed inserts the Free tier first, then the ALTER DEFAULT references its ID)

3. **Quota Enforcement Service**
   - `QuotaService` in application layer -- central place to check all tier limits
   - Methods: `check_document_quota(tenant_id, user_id)`, `check_template_limit(tenant_id)`, `check_user_limit(tenant_id)`, `check_bulk_limit(tenant_id, user_id, requested_count)`, `check_share_limit(template_id)`
   - Per-user `bulk_generation_limit` override remains -- if set on User, it wins over tier's `bulk_generation_limit`
   - Returns the effective limit and current usage, or raises `QuotaExceededError`

4. **Domain Exception: QuotaExceededError**
   - New exception in `domain/exceptions.py`
   - Fields: `limit_type` (documents, templates, users, bulk, shares), `limit_value`, `current_usage`, `message`
   - Presentation layer maps to HTTP 429 with structured error body

5. **Integration into Existing Services**
   - `DocumentService.generate_single()` -- call `quota_service.check_document_quota()` BEFORE generation
   - `DocumentService.generate_bulk()` -- call `quota_service.check_document_quota()` (for total: current + requested) and `check_bulk_limit()` BEFORE generation
   - `DocumentService.parse_excel_data()` -- check_bulk_limit against tier (replaces hardcoded `self._bulk_limit` check)
   - `TemplateService.upload_template()` -- call `quota_service.check_template_limit()` BEFORE upload
   - `TemplateService.share_template()` -- call `quota_service.check_share_limit()` BEFORE share
   - User creation endpoint -- call `quota_service.check_user_limit()` BEFORE creating user

6. **API Endpoints**
   - `GET /api/v1/tiers` -- list all active tiers (public, for pricing page)
   - `GET /api/v1/tenant/tier` -- current tenant's tier with usage summary (limits vs current)
   - `PUT /api/v1/admin/tenant/{tenant_id}/tier` -- superadmin: change a tenant's tier (out of scope for now -- placeholder for billing integration)
   - Existing `GET /api/v1/usage` response enriched: add `limit` and `percentage_used` fields from tier

7. **Alembic Migration `005_subscription_tiers`**
   - Creates `subscription_tiers` table
   - Inserts three seed rows (Free, Pro, Enterprise) with deterministic UUIDs
   - Adds `tier_id` column to `tenants` with FK, default = Free tier UUID
   - Backfills existing tenants to Free tier

8. **Frontend**
   - Tier info card on dashboard: "Your Plan: Free -- 23/50 documents this month" with progress bar
   - Upgrade prompt when approaching limit (>80% usage)
   - Quota exceeded error handling: show clear modal with tier info + "Contact admin to upgrade"
   - Admin: tenant settings page shows current tier
   - Template upload: show "X/Y templates used" indicator
   - User management: show "X/Y users" indicator

9. **Tests**
   - Unit: `test_quota_service.py` -- all quota checks with various tier configs, edge cases (at limit, over limit, unlimited = None sentinel, per-user override)
   - Unit: extend `test_document_service.py` -- verify quota check is called before generation
   - Unit: extend `test_template_service.py` -- verify template limit check before upload
   - Integration: `test_tier_api.py` -- list tiers, get tenant tier, quota exceeded scenarios
   - Fake: `FakeSubscriptionTierRepository`, `FakeQuotaService` (or compose from fakes)

### Out of Scope

- **Billing / payment integration** (Stripe, etc.) -- this is plan assignment, not payment
- **Self-service tier upgrade UI** -- admin/superadmin changes tier manually for now
- **Rate limiting per tier** (separate change: `rate-limits-per-tier`) -- rate limits are request-frequency throttling, not monthly quotas
- **Tier change audit logging** -- can be added when the admin endpoint is built
- **Prorated billing on mid-month tier changes** -- free tier changes take effect immediately, usage resets at month boundary
- **Custom tiers per tenant** -- the tier table supports it structurally, but the UI does not expose tier creation
- **Usage alerts / email notifications** when approaching quota

## Approach

### ADR-1: Database Table vs. Hardcoded Tiers

**Decision**: Database table (`subscription_tiers`).

**Why**: A SaaS product WILL change its tier definitions over time -- new tiers, adjusted limits, promotional plans, per-customer enterprise deals. Hardcoded tiers require a code deploy to change a limit. A DB table lets an admin adjust limits via a future admin UI or direct DB update without redeploying. The seed migration provides sensible defaults.

**Tradeoff**: Slightly more complex than a Python enum, but the flexibility is non-negotiable for SaaS.

### ADR-2: Tier Assigned to Tenant, Not User

**Decision**: `tier_id` on `tenants`, not on `users`.

**Why**: SigDoc is multi-tenant with shared resources. All users in a tenant share the same document quota, template pool, and user slots. Billing is per-organization, not per-seat. Individual users do not choose their plan -- the tenant admin (or SigDoc superadmin) does.

**Consequence**: The per-user `bulk_generation_limit` on User remains as an OVERRIDE. It is the only per-user limit -- everything else is tenant-wide. This is intentional: an admin may want to boost a specific power user's bulk cap without upgrading the entire tenant.

### ADR-3: QuotaService as Separate Service (Not Inside DocumentService)

**Decision**: Dedicated `QuotaService` in the application layer.

**Why**: Quota checking needs to happen across multiple services (DocumentService, TemplateService, user creation). Embedding it in DocumentService would create coupling and duplication. A QuotaService centralizes all "can this tenant do X?" logic in one place.

**Dependencies**: QuotaService needs `SubscriptionTierRepository` (to load the tier), `UsageRepository` (to get current month usage), `TemplateRepository` (to count templates), `UserRepository` (to count users), and optionally the User entity (for per-user override).

**Injection**: QuotaService is injected into DocumentService and TemplateService via the DI factory in `services/__init__.py`. For user creation (which happens in the router directly via UserRepository), QuotaService is injected via `Depends()`.

### ADR-4: "Unlimited" Represented as None/NULL

**Decision**: When a tier limit is `None` (NULL in DB), it means unlimited.

**Why**: Simpler than using a magic number like `999999999`. The quota check becomes: `if limit is None: return (allowed)`. This is a common pattern (e.g., GitHub plans, Slack plans). Enterprise tier will have `max_templates=NULL`, `max_users=NULL`, `max_template_shares=NULL`.

**Consequence**: All quota check methods must handle `None` as "no limit". The domain entity uses `int | None` for limit fields.

### ADR-5: Quota Check BEFORE Operation (Fail-Fast)

**Decision**: Check quota before starting the operation, not after.

**Why**: It would be a terrible UX to process a 25-row bulk generation, upload all files to MinIO, then discover the tenant is over quota and have to roll everything back. Fail-fast at the top of the service method.

**Edge case -- concurrent requests**: Two requests could both pass the quota check simultaneously and both succeed, pushing the tenant slightly over quota. This is acceptable for an MVP. The over-quota amount is bounded (at most one extra request's worth). If this becomes a problem, a `SELECT ... FOR UPDATE` on the usage count or an optimistic lock can be added later.

### ADR-6: Deterministic UUIDs for Seed Tiers

**Decision**: The three default tiers use hardcoded UUIDs in the migration (UUID v5 from a namespace + tier slug).

**Why**: The `tier_id` DEFAULT on `tenants.tier_id` must reference a known UUID. If we used random UUIDs, the migration would need a subquery for the DEFAULT, which is non-portable. Deterministic UUIDs also make it trivial to reference specific tiers in tests and seed scripts.

### Schema Design

#### `subscription_tiers` table

```
subscription_tiers
+-- id                       UUID PK (deterministic for seed tiers)
+-- name                     VARCHAR(100) NOT NULL -- "Free", "Pro", "Enterprise"
+-- slug                     VARCHAR(50) UNIQUE NOT NULL -- "free", "pro", "enterprise"
+-- monthly_document_limit   INTEGER NULL -- NULL = unlimited
+-- max_templates            INTEGER NULL -- NULL = unlimited
+-- max_users                INTEGER NULL -- NULL = unlimited
+-- bulk_generation_limit    INTEGER NOT NULL DEFAULT 10
+-- max_template_shares      INTEGER NULL -- NULL = unlimited
+-- is_active                BOOLEAN NOT NULL DEFAULT TRUE
+-- created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
+-- updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
```

#### Default tier values

| Field | Free | Pro | Enterprise |
|-------|------|-----|------------|
| monthly_document_limit | 50 | 500 | 5000 |
| max_templates | 5 | 50 | NULL (unlimited) |
| max_users | 3 | 20 | NULL (unlimited) |
| bulk_generation_limit | 5 | 25 | 100 |
| max_template_shares | 5 | 50 | NULL (unlimited) |

#### `tenants` table change

```sql
ALTER TABLE tenants
  ADD COLUMN tier_id UUID NOT NULL
    REFERENCES subscription_tiers(id)
    DEFAULT '{free_tier_uuid}';
```

### Clean Architecture Layers

```
domain/
+-- entities/subscription_tier.py       -- SubscriptionTier dataclass
+-- ports/subscription_tier_repository.py -- SubscriptionTierRepository ABC
+-- exceptions.py                       -- + QuotaExceededError

application/
+-- services/quota_service.py           -- QuotaService (check all limits)

infrastructure/
+-- persistence/models/subscription_tier.py   -- SubscriptionTierModel
+-- persistence/repositories/subscription_tier_repository.py

presentation/
+-- api/v1/tiers.py                     -- Tier endpoints
+-- schemas/tier.py                     -- Pydantic schemas
```

### Integration Points

1. **DocumentService.generate_single()** -- insert quota check at top:
   ```python
   await self._quota_service.check_document_quota(tenant_id, user_id)
   ```

2. **DocumentService.generate_bulk()** -- insert quota check at top:
   ```python
   await self._quota_service.check_document_quota(tenant_id, user_id, additional=len(rows))
   await self._quota_service.check_bulk_limit(tenant_id, user_id, len(rows))
   ```

3. **DocumentService.parse_excel_data()** -- replace `self._bulk_limit` check:
   ```python
   # Old: if len(rows) > self._bulk_limit: raise BulkLimitExceededError
   # New: await self._quota_service.check_bulk_limit(tenant_id, user_id, len(rows))
   ```

4. **TemplateService.upload_template()** -- insert at top:
   ```python
   await self._quota_service.check_template_limit(tenant_id)
   ```

5. **TemplateService.share_template()** -- insert at top:
   ```python
   await self._quota_service.check_share_limit(template_id)
   ```

6. **Users router (create user)** -- inject QuotaService via Depends:
   ```python
   await quota_service.check_user_limit(tenant_id)
   ```

### Backward Compatibility

- `QuotaService` is optional (None default) in DocumentService and TemplateService constructors. When None, no quota check is performed -- all existing 188 tests pass without modification.
- The `bulk_generation_limit` parameter on DocumentService remains for backward compat but is superseded by `QuotaService.check_bulk_limit()` when quota_service is present.
- Per-user `bulk_generation_limit` on User still works -- QuotaService checks it as an override.

### Frontend Changes

1. **Dashboard tier card**: New component in `features/usage/` (extends existing usage widget)
   - Shows: plan name, docs used/limit with progress bar, templates used/limit, users used/limit
   - Color coding: green (<60%), yellow (60-80%), red (>80%)
   - "Upgrade" button when on Free tier (links to contact/pricing -- no self-service yet)

2. **Quota exceeded modal**: Reusable component
   - Triggered when any API returns 429 with `limit_type` in body
   - Shows which limit was hit, current usage, and tier info
   - CTA: "Contact your administrator to upgrade"

3. **Template upload indicator**: Small badge "3/5 templates" near upload button

4. **User management indicator**: Small badge "2/3 users" in user list header (admin)

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Concurrent requests bypass quota (TOCTOU) | Medium | Low | Acceptable for MVP. Over-quota bounded to one request's worth. Add row-level lock later if needed. |
| Migration fails on existing data (NULL tier_id) | Low | High | Migration inserts Free tier FIRST, then adds column with DEFAULT. No NULL values possible. |
| QuotaService adds latency to every generation | Low | Medium | Single DB query to load tier (cacheable). Usage aggregation query already exists and is indexed. |
| Enterprise customers need custom limits | Medium | Medium | DB table supports custom tiers. Create a new tier row with custom limits, assign to tenant. No code change needed. |
| Frontend quota display stale after generation | Low | Low | Refetch usage after mutation (React Query invalidation). |

## Dependencies

- **Requires**: `usage-tracking-and-audit` (DONE -- provides UsageRepository with monthly aggregation queries)
- **Enables**: `rate-limits-per-tier` (can read tier to determine rate limit multiplier)
- **Migration**: `005` -- depends on 001-004 existing schema

## Success Criteria

1. Three default tiers (Free, Pro, Enterprise) exist in the database after migration
2. Every existing tenant is assigned the Free tier
3. `GET /api/v1/tiers` returns all active tiers with their limits
4. `GET /api/v1/tenant/tier` returns the current tenant's tier + usage summary
5. Document generation fails with 429 + QuotaExceededError when monthly limit exceeded
6. Template upload fails with 429 when template limit exceeded
7. User creation fails with 429 when user limit exceeded
8. Bulk generation respects tier's bulk_generation_limit (with per-user override)
9. Template sharing respects tier's max_template_shares
10. Frontend dashboard shows tier card with usage vs limits
11. Frontend shows quota exceeded modal on 429 responses
12. All existing 188 tests continue to pass (backward compat)
13. New tests: quota service unit tests, tier API integration tests, quota enforcement integration tests
