# Design: rate-limits-per-tier

## Overview

Technical design for adding per-tier dynamic rate limiting to SigDoc. Extends the existing slowapi infrastructure with tier-aware limit resolution and per-tenant keying.

## ADRs

### ADR-1: Rate limit columns on subscription_tiers (not separate table)

**Decision**: Store rate limit values directly as columns on the `subscription_tiers` table rather than a separate `rate_limit_profiles` table.

**Rationale**: There are exactly 4 rate limit categories (login, refresh, generate, bulk) and 3 tiers. A separate table adds a join with no benefit — the cardinality is fixed and small. The tier entity already holds all other plan limits (document quota, template cap, etc.), so rate limits belong alongside them.

**Tradeoff**: If we add 20+ rate-limited endpoint categories in the future, the table becomes wide. Acceptable risk — we can refactor to a JSON column or separate table if that happens.

### ADR-2: Per-tenant keying for authenticated endpoints, IP for login

**Decision**: Use `tenant_id` from JWT as the rate limit key for authenticated endpoints. Keep `get_remote_address` (IP) for the login endpoint.

**Rationale**: In a multi-tenant SaaS, rate limits should be per-tenant, not per-IP. Multiple employees behind a corporate NAT should not share a rate limit counter, and a tenant using VPN should not get a fresh counter on each IP change. Login is the exception — there is no JWT yet, so IP-based keying is the only option.

**Implementation**: Create two key functions:
- `get_tenant_id_from_request(request)` — extracts tenant_id from the Authorization header JWT. Falls back to IP if JWT is missing/invalid.
- Keep using `get_remote_address` for login.

### ADR-3: Dynamic limit via slowapi callable pattern

**Decision**: Use slowapi's `limit(callable)` pattern where the callable receives the `request` object and returns the limit string.

**Rationale**: slowapi's `@limiter.limit()` decorator accepts either a string (`"5/minute"`), a callable returning a string (`lambda: "5/minute"`), or a callable taking the request (`def fn(request) -> str`). The current codebase uses `lambda: get_settings().rate_limit_X`. We upgrade to a function that receives the request, extracts the tenant_id, loads the tier, and returns the tier-specific limit.

**Key insight**: The `limit()` decorator's callable signature is `(request_or_string) -> str`. When it receives a callable, slowapi calls it with no args if it accepts 0 params, or with `(request,)` if it accepts 1 param. We need the request to extract the JWT, so we use the 1-param form.

### ADR-4: TTL cache for tier lookups (not per-request DB query)

**Decision**: Cache tier data per `tenant_id` with a 60-second TTL using `cachetools.TTLCache`.

**Rationale**: Every rate-limited request would need to resolve tenant_id -> tier -> rate limit string. Without caching, this adds a DB query per request. With TTL cache, the first request per tenant per minute hits the DB; subsequent requests use the cached tier. 60 seconds balances freshness (admin changes tiers) with performance.

**Dependency**: `cachetools` (already a transitive dependency of google-auth, but we'll add it explicitly to requirements if needed).

**Alternative considered**: `functools.lru_cache` — rejected because it has no TTL and would cache stale tier data forever until restart.

### ADR-5: Login rate limit remains global (from Settings)

**Decision**: The login endpoint continues to use `Settings.rate_limit_login` as the limit value, keyed by IP.

**Rationale**: At login time, we don't know which tenant the user belongs to (the email hasn't been validated yet). We could look up the user's tenant from the email, but that adds a DB query before rate limiting — which defeats the purpose of rate limiting (protecting the DB). The global login limit is acceptable because it protects against brute-force attacks per-IP.

## Schema Changes

### Migration 006: Add rate limit columns to subscription_tiers

```sql
ALTER TABLE subscription_tiers
  ADD COLUMN rate_limit_login VARCHAR(50) NOT NULL DEFAULT '5/minute',
  ADD COLUMN rate_limit_refresh VARCHAR(50) NOT NULL DEFAULT '10/minute',
  ADD COLUMN rate_limit_generate VARCHAR(50) NOT NULL DEFAULT '20/minute',
  ADD COLUMN rate_limit_bulk VARCHAR(50) NOT NULL DEFAULT '5/minute';

-- Seed per-tier values
UPDATE subscription_tiers SET
  rate_limit_login = '5/minute',
  rate_limit_refresh = '10/minute',
  rate_limit_generate = '10/minute',
  rate_limit_bulk = '2/minute'
WHERE slug = 'free';

UPDATE subscription_tiers SET
  rate_limit_login = '10/minute',
  rate_limit_refresh = '20/minute',
  rate_limit_generate = '30/minute',
  rate_limit_bulk = '10/minute'
WHERE slug = 'pro';

UPDATE subscription_tiers SET
  rate_limit_login = '20/minute',
  rate_limit_refresh = '30/minute',
  rate_limit_generate = '60/minute',
  rate_limit_bulk = '20/minute'
WHERE slug = 'enterprise';
```

### Domain Entity Update

```python
@dataclass(frozen=True)
class SubscriptionTier:
    # ... existing fields ...
    rate_limit_login: str = "5/minute"
    rate_limit_refresh: str = "10/minute"
    rate_limit_generate: str = "20/minute"
    rate_limit_bulk: str = "5/minute"
```

## Component Design

### 1. Rate Limit Resolver (`rate_limit.py`)

The `rate_limit.py` module grows from 4 lines to a full module with:

```python
# Key functions
def get_tenant_key(request: Request) -> str:
    """Extract tenant_id from JWT for per-tenant rate limiting.
    Falls back to IP address if JWT is missing/invalid."""

# Tier cache
_tier_cache: TTLCache[str, SubscriptionTier] = TTLCache(maxsize=256, ttl=60)

async def _resolve_tier(tenant_id: str) -> SubscriptionTier | None:
    """Load tier for tenant_id, checking cache first."""

# Dynamic limit functions (one per endpoint category)
def tier_limit_generate(request: Request) -> str:
    """Return the generate rate limit for the request's tenant tier."""

def tier_limit_bulk(request: Request) -> str:
    """Return the bulk rate limit for the request's tenant tier."""

def tier_limit_refresh(request: Request) -> str:
    """Return the refresh rate limit for the request's tenant tier."""
```

**Challenge**: slowapi limit callables are synchronous, but tier lookup is async (DB query). 

**Solution**: The tier cache is populated asynchronously during the first authenticated request via a FastAPI middleware or dependency. The synchronous limit callable reads from the cache only. If the cache misses, it falls back to the global Settings value (synchronous, always available).

**Concrete approach**:
1. Add a lightweight middleware/dependency that runs before rate limiting: it decodes the JWT, loads the tier (async), and stores it on `request.state.tier`.
2. The limit callable reads `request.state.tier.rate_limit_generate` (sync).
3. If `request.state.tier` is not set (unauthenticated, cache miss), falls back to `get_settings().rate_limit_generate`.

### 2. Tier Preload Middleware

A FastAPI middleware or dependency that:
1. Checks for `Authorization` header
2. Decodes JWT to get `tenant_id`
3. Looks up tier from cache (TTLCache) or DB
4. Stores on `request.state.tier`

This runs BEFORE slowapi's middleware processes the rate limit decorator.

**Middleware ordering**: FastAPI processes middleware in LIFO order (last added = outermost). SlowAPIMiddleware is already added in `main.py`. We need our tier preload middleware to run BEFORE slowapi, so we add it AFTER slowapi in the code (which makes it the outer middleware).

### 3. Limiter Configuration Update

```python
# Before (current)
limiter = Limiter(key_func=get_remote_address)

# After
limiter = Limiter(key_func=get_tenant_key)
```

The `get_tenant_key` function extracts `tenant_id` from the JWT. For unauthenticated requests (login), it falls back to `get_remote_address`.

**Per-endpoint key override**: Login endpoint uses `@limiter.limit(..., key_func=get_remote_address)` to override the default tenant-based keying.

### 4. API Schema Updates

`TierPublicSchema` gets 4 new fields:
```python
rate_limit_login: str
rate_limit_refresh: str
rate_limit_generate: str
rate_limit_bulk: str
```

### 5. SQLAlchemy Model Update

`SubscriptionTierModel` gets 4 new mapped columns matching the migration.

### 6. Repository Mapper Update

`_to_entity()` in `subscription_tier_repository.py` includes the new fields.

### 7. Test Fake Update

`FakeSubscriptionTierRepository` default tiers include rate limit fields.

## Data Flow

```
Request → TierPreloadMiddleware → SlowAPIMiddleware → Route Handler
              |                        |
              v                        v
         JWT decode              limiter.limit(callable)
         tenant_id →                    |
         cache/DB →              callable(request) →
         request.state.tier      request.state.tier.rate_limit_X
                                 or fallback to Settings
```

## File Impact Summary

| File | Change |
|------|--------|
| `domain/entities/subscription_tier.py` | Add 4 rate limit fields |
| `infrastructure/persistence/models/subscription_tier.py` | Add 4 mapped columns |
| `infrastructure/persistence/repositories/subscription_tier_repository.py` | Update `_to_entity()` mapper |
| `presentation/middleware/rate_limit.py` | Major rewrite: tenant keying, tier-aware limit functions, tier preload |
| `presentation/api/v1/auth.py` | Update limit decorators to use dynamic functions |
| `presentation/api/v1/documents.py` | Update limit decorators to use dynamic functions |
| `presentation/schemas/tier.py` | Add rate limit fields to `TierPublicSchema` |
| `presentation/api/v1/tiers.py` | Include rate limit fields in tier list response |
| `config.py` | No changes (retain existing global defaults as fallbacks) |
| `main.py` | Add tier preload middleware after SlowAPIMiddleware |
| `alembic/versions/006_rate_limits_per_tier.py` | New migration |
| `tests/fakes/fake_subscription_tier_repository.py` | Update default tiers with rate limit fields |
| `tests/integration/test_rate_limit.py` | Extend with tier-specific tests |
| `tests/unit/test_rate_limit_resolver.py` | New: unit tests for limit resolution logic |
