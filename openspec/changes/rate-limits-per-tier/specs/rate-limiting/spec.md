# Spec: rate-limits-per-tier

## Overview

Delta spec for dynamic per-tier rate limiting. Extends the existing slowapi-based rate limiting to resolve limits from the tenant's subscription tier at request time.

## Definitions

- **Rate limit profile**: The set of rate limit strings (e.g., `"5/minute"`) associated with a subscription tier for each rate-limited endpoint category.
- **Endpoint category**: A logical grouping of endpoints sharing the same rate limit: `login`, `refresh`, `generate`, `bulk`.
- **Tier-aware limit**: A rate limit value resolved dynamically from the authenticated tenant's subscription tier, as opposed to a global fixed value.

## Requirements

### REQ-RL-01: Tier rate limit columns

The `subscription_tiers` table MUST include the following columns:
- `rate_limit_login` (VARCHAR(50), NOT NULL, default `"5/minute"`)
- `rate_limit_refresh` (VARCHAR(50), NOT NULL, default `"10/minute"`)
- `rate_limit_generate` (VARCHAR(50), NOT NULL, default `"20/minute"`)
- `rate_limit_bulk` (VARCHAR(50), NOT NULL, default `"5/minute"`)

### REQ-RL-02: Seed data

Migration MUST seed rate limit values per tier:

| Tier | login | refresh | generate | bulk |
|------|-------|---------|----------|------|
| Free | 5/minute | 10/minute | 10/minute | 2/minute |
| Pro | 10/minute | 20/minute | 30/minute | 10/minute |
| Enterprise | 20/minute | 30/minute | 60/minute | 20/minute |

### REQ-RL-03: Per-tenant rate limit keying

For authenticated endpoints (generate, bulk, refresh), the rate limiter MUST key by `tenant_id` extracted from the JWT, NOT by IP address.

For unauthenticated endpoints (login), the rate limiter MUST continue to key by IP address.

### REQ-RL-04: Dynamic limit resolution

For authenticated endpoints, the rate limiter MUST resolve the limit string from the tenant's subscription tier at request time. The `SubscriptionTier` entity MUST expose `rate_limit_login`, `rate_limit_refresh`, `rate_limit_generate`, and `rate_limit_bulk` fields.

### REQ-RL-05: Fallback behavior

If the tenant's tier cannot be resolved (missing JWT, invalid tenant, no tier assigned), the rate limiter MUST fall back to the global limits defined in `Settings` (existing behavior).

### REQ-RL-06: API exposure

The `TierPublicSchema` MUST include the rate limit fields so clients can display tier rate limit information.

### REQ-RL-07: Cache tier lookups

Tier-to-rate-limit resolution SHOULD be cached with a TTL of 60 seconds to avoid per-request DB queries. The cache MUST be keyed by `tenant_id`.

### REQ-RL-08: Existing global settings retained

The global `rate_limit_*` settings in `Settings` (config.py) MUST be retained as fallback defaults. They MUST NOT be removed.

## Scenarios

### SC-RL-01: Free tier tenant hits generate rate limit

```
Given a tenant on the Free tier (rate_limit_generate = "10/minute")
When the tenant makes 10 successful POST /documents/generate requests within 1 minute
Then the 11th request MUST return HTTP 429
And the X-RateLimit-Limit header MUST show "10"
```

### SC-RL-02: Pro tier tenant has higher generate limit

```
Given a tenant on the Pro tier (rate_limit_generate = "30/minute")
When the tenant makes 11 POST /documents/generate requests within 1 minute
Then all 11 requests MUST succeed (HTTP 201)
And the X-RateLimit-Remaining header MUST show "19"
```

### SC-RL-03: Enterprise tier tenant has generous bulk limit

```
Given a tenant on the Enterprise tier (rate_limit_bulk = "20/minute")
When the tenant makes 15 POST /documents/generate-bulk requests within 1 minute
Then all 15 requests MUST succeed
```

### SC-RL-04: Login endpoint uses IP-based keying

```
Given two users from different tenants sharing the same IP address
When user A makes 5 login attempts (Free tier login limit)
Then user A's 6th login attempt from the same IP MUST return HTTP 429
And user B's login attempt from a DIFFERENT IP MUST succeed
```

### SC-RL-05: Fallback to global limit when tier unavailable

```
Given a request to an authenticated endpoint
When the tenant's tier cannot be resolved (e.g., tier_id is NULL)
Then the rate limiter MUST apply the global Settings.rate_limit_* value
And the request MUST NOT fail with a 500 error
```

### SC-RL-06: Rate limits keyed per tenant, not per IP

```
Given tenant A (Free tier) and tenant B (Pro tier) behind the same IP
When tenant A makes 10 generate requests (hitting Free limit)
Then tenant A's 11th request MUST return HTTP 429
And tenant B's generate requests MUST still succeed (separate counter)
```

### SC-RL-07: Tier rate limits visible in public API

```
Given a GET /tiers request
When the response is returned
Then each tier object MUST include rate_limit_login, rate_limit_refresh, rate_limit_generate, and rate_limit_bulk fields
```

### SC-RL-08: Tenant tier endpoint shows rate limits

```
Given an authenticated GET /tiers/tenant request
When the response is returned
Then the tier object MUST include rate limit fields for the tenant's current tier
```
