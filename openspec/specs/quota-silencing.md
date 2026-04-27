# Capability: quota-silencing

## Purpose

Defines the `_QUOTA_DISABLED` flag semantics on `QuotaService` for Nivel A of the CAINCO acquisition. When the flag is `True` (the Nivel A default), all quota-enforcement methods short-circuit without performing any database query or raising any exception. The `get_tier_for_tenant` method is explicitly exempt from silencing — it remains live because `TierPreloadMiddleware` depends on it for per-tier rate-limit resolution. This spec also pins the reversibility invariant: flipping `_QUOTA_DISABLED` to `False` (e.g., in a test or a future Nivel B rollback) restores original enforcement behavior.

## Requirements

### REQ-QSI-01: _QUOTA_DISABLED class-level constant
`QuotaService` (`backend/src/app/application/services/quota_service.py`) MUST have a class-level constant `_QUOTA_DISABLED = True`. Setting this constant to `False` MUST re-enable original quota enforcement logic. The constant MUST be defined at the class scope so tests can override it per-instance or per-class without patching a module global.

### REQ-QSI-02: check_user_limit is a no-op when disabled
`QuotaService.check_user_limit(...)` MUST return without raising any exception when `_QUOTA_DISABLED` is `True`. No database query MUST be performed in this path.

### REQ-QSI-03: check_document_quota is a no-op when disabled
`QuotaService.check_document_quota(...)` MUST return without raising any exception when `_QUOTA_DISABLED` is `True`. No database query MUST be performed in this path.

### REQ-QSI-04: check_bulk_limit is a no-op when disabled
`QuotaService.check_bulk_limit(...)` MUST return without raising any exception when `_QUOTA_DISABLED` is `True`. No database query MUST be performed in this path.

### REQ-QSI-05: check_template_limit is a no-op when disabled
`QuotaService.check_template_limit(...)` MUST return without raising any exception when `_QUOTA_DISABLED` is `True`. No database query MUST be performed in this path.

### REQ-QSI-06: check_share_limit is a no-op when disabled
`QuotaService.check_share_limit(...)` MUST return without raising any exception when `_QUOTA_DISABLED` is `True`. No database query MUST be performed in this path.

### REQ-QSI-07: get_usage_summary returns no-limits stub when disabled
`QuotaService.get_usage_summary(...)` MUST return a stub response indicating no active limits when `_QUOTA_DISABLED` is `True`. The stub MUST include a `limit: null` (or equivalent sentinel) for every tracked resource. No database query MUST be performed in this path.

### REQ-QSI-08: get_tier_for_tenant is NOT silenced
`QuotaService.get_tier_for_tenant(tenant_id)` MUST NOT be affected by `_QUOTA_DISABLED`. It MUST always execute its full implementation, querying the database and returning the actual tier for the given tenant. This is required because `TierPreloadMiddleware` uses this method to resolve per-tenant rate-limit tiers.

### REQ-QSI-09: No HTTP 429 due to quota when disabled
With `_QUOTA_DISABLED = True`, generating any quantity of documents (single or bulk) MUST NOT result in an HTTP 429 response attributable to quota enforcement. Slowapi request-rate limiting is a separate code path and MAY still return 429.

### REQ-QSI-10: No HTTP 429 due to user-count quota when disabled
With `_QUOTA_DISABLED = True`, an admin creating users MUST NOT receive HTTP 429 due to user-count quota. The `create_user` handler MAY still be subject to slowapi rate limiting.

### REQ-QSI-11: Disabling is reversible
Setting `_QUOTA_DISABLED = False` (e.g., in a unit test override or a future Nivel B change) MUST restore quota enforcement such that `check_document_quota`, `check_user_limit`, `check_bulk_limit`, `check_template_limit`, and `check_share_limit` raise `QuotaExceededError` when the relevant limit is exceeded. This invariant MUST be verified by at least one unit test that sets `_QUOTA_DISABLED = False` on the instance.

## Scenarios

### SCEN-QSI-01: Document generation ignores monthly limit when quota disabled
**Given**: `_QUOTA_DISABLED = True` AND a tenant is on the Free tier with `monthly_document_limit = 100` AND the tenant has already generated 100 documents this month  
**When**: An authenticated user generates 1 more document  
**Then**: The generation succeeds (200/202); no `QuotaExceededError` is raised; no 429 is returned due to quota  
*(Verifies REQ-QSI-03, REQ-QSI-09)*

### SCEN-QSI-02: Bulk generation ignores bulk limit when quota disabled
**Given**: `_QUOTA_DISABLED = True` AND a tenant is on the Free tier with `bulk_generation_limit = 10`  
**When**: An admin generates a bulk batch of 50 documents  
**Then**: The bulk generation succeeds; no 429 is returned due to quota  
*(Verifies REQ-QSI-04, REQ-QSI-09)*

### SCEN-QSI-03: User creation ignores user-count limit when quota disabled
**Given**: `_QUOTA_DISABLED = True` AND a tenant is on the Free tier with `max_users = 5` AND 10 users already exist  
**When**: An admin sends `POST /api/v1/users` to create the 11th user  
**Then**: The response is 201 Created; no 429 is returned due to quota  
*(Verifies REQ-QSI-02, REQ-QSI-10)*

### SCEN-QSI-04: get_tier_for_tenant returns actual tier data
**Given**: `_QUOTA_DISABLED = True` AND the singleton tenant has a tier row in the database  
**When**: `QuotaService.get_tier_for_tenant(tenant_id)` is called  
**Then**: It returns the actual tier object from the database (not a stub); `TierPreloadMiddleware` can use this to set per-tenant rate limits  
*(Verifies REQ-QSI-08)*

### SCEN-QSI-05: Flipping _QUOTA_DISABLED to False restores enforcement
**Given**: A `QuotaService` instance with `_QUOTA_DISABLED` overridden to `False` AND a tenant has exceeded its `monthly_document_limit`  
**When**: `check_document_quota(...)` is called for that tenant  
**Then**: A `QuotaExceededError` is raised  
*(Verifies REQ-QSI-11)*

### SCEN-QSI-06: get_usage_summary returns no-limits stub when disabled
**Given**: `_QUOTA_DISABLED = True`  
**When**: `QuotaService.get_usage_summary(tenant_id, user_id)` is called  
**Then**: The return value contains `limit: null` (or equivalent no-limits sentinel) for documents, users, and templates; no database query is performed  
*(Verifies REQ-QSI-07)*
