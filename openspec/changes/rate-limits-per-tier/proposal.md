# Proposal: rate-limits-per-tier

## Intent

Replace the current global rate limiting (same limits for all users regardless of subscription) with **tier-aware dynamic rate limits**. Each subscription tier (Free, Pro, Enterprise) gets its own rate limit profile, resolved at request time from the tenant's tier.

## Problem

Today, slowapi rate limits are configured globally in `Settings` (e.g., `rate_limit_login="5/minute"`) and applied identically to every request via `@limiter.limit(lambda: get_settings().rate_limit_login)`. This means a Free tenant consuming 5 API calls blocks at the same threshold as an Enterprise tenant paying for premium access. There is no incentive for tenants to upgrade — the rate limit experience is identical across tiers.

Additionally, the current `key_func=get_remote_address` keys rate limits by IP address, which is wrong for a multi-tenant SaaS: multiple users behind a corporate NAT share one IP, and a single user on a VPN changes IP frequently.

## Scope

- **In scope**: Rate limit columns on `subscription_tiers` table, dynamic limit resolution via tenant tier, per-tenant keying (tenant_id instead of IP), rate limit profile exposed in `/tiers` and `/tiers/tenant` APIs, migration, tests.
- **Out of scope**: Per-user rate limit overrides (future), Redis-backed rate limit storage (current MemoryStorage is fine for single-instance), custom rate limit windows (always per-minute), admin UI for editing rate limits.

## Approach

1. **Schema extension**: Add `rate_limit_login`, `rate_limit_generate`, `rate_limit_bulk` columns to `subscription_tiers` table (VARCHAR, e.g., `"5/minute"`). Seed with per-tier defaults.
2. **Domain entity extension**: Add corresponding fields to `SubscriptionTier` dataclass.
3. **Dynamic limit resolver**: Create a `get_tier_rate_limit(request, endpoint_key)` function that extracts `tenant_id` from the JWT in the request, loads the tier (with caching), and returns the limit string.
4. **Per-tenant key function**: Replace `get_remote_address` with a custom `key_func` that extracts `tenant_id` from the JWT. Fall back to IP for unauthenticated endpoints (login).
5. **Decorator update**: Change `@limiter.limit(lambda: get_settings().rate_limit_X)` to `@limiter.limit(dynamic_limit_function)` where the function receives the `request` and resolves the limit from the tier.
6. **API exposure**: Include rate limit fields in `TierPublicSchema` so the frontend knows the limits.
7. **Response headers**: slowapi already sets `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers — these will automatically reflect the tier-specific values.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| JWT parsing in key_func adds latency | Low | Low | JWT decode is ~0.1ms; already done in auth middleware |
| Tier cache staleness after admin changes tier limits | Medium | Low | TTL-based cache (60s); admin changes are rare |
| Login endpoint has no JWT (unauthenticated) | Certain | Medium | Fall back to IP-based keying + global Settings limit for login; tier limits apply only to authenticated endpoints |
| slowapi dynamic limit function signature | Low | Medium | slowapi's `limit()` accepts `callable(str)` or `callable(request) -> str`; verify signature |

## Success Criteria

- Free/Pro/Enterprise tenants receive different 429 thresholds on generate and bulk endpoints
- Login endpoint remains IP-based with configurable global limit
- Existing 231 tests pass; new tests cover tier-specific rate limiting
- Rate limit values visible in `/tiers` API response
