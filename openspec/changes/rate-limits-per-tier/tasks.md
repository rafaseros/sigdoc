# Tasks: rate-limits-per-tier

## Phase 1: Schema & Domain (foundation)

### Task 1.1: Add rate limit fields to SubscriptionTier entity
- **File**: `backend/src/app/domain/entities/subscription_tier.py`
- **Action**: Add 4 fields to the frozen dataclass: `rate_limit_login: str = "5/minute"`, `rate_limit_refresh: str = "10/minute"`, `rate_limit_generate: str = "20/minute"`, `rate_limit_bulk: str = "5/minute"`
- **Spec**: REQ-RL-01, REQ-RL-04
- **Test**: Unit test asserting default values on new SubscriptionTier()
- [x] Done

### Task 1.2: Add rate limit columns to SubscriptionTierModel
- **File**: `backend/src/app/infrastructure/persistence/models/subscription_tier.py`
- **Action**: Add 4 `Mapped[str]` columns: `rate_limit_login`, `rate_limit_refresh`, `rate_limit_generate`, `rate_limit_bulk` with `String(50)`, `nullable=False`, `server_default` matching entity defaults
- **Spec**: REQ-RL-01
- [x] Done

### Task 1.3: Update repository entity mapper
- **File**: `backend/src/app/infrastructure/persistence/repositories/subscription_tier_repository.py`
- **Action**: Update `_to_entity()` to include the 4 new rate limit fields from the model
- **Spec**: REQ-RL-04
- [x] Done

### Task 1.4: Create migration 006
- **File**: `backend/alembic/versions/006_rate_limits_per_tier.py`
- **Action**: ALTER TABLE to add 4 VARCHAR(50) columns with defaults, UPDATE to seed per-tier values (Free: strict, Pro: moderate, Enterprise: generous per REQ-RL-02)
- **Spec**: REQ-RL-01, REQ-RL-02
- [x] Done

### Task 1.5: Update test fakes
- **File**: `backend/tests/fakes/fake_subscription_tier_repository.py`
- **Action**: Update `_DEFAULT_TIERS` to include rate limit fields with tier-appropriate values matching migration seed data
- **Spec**: REQ-RL-02
- [x] Done

## Phase 2: Rate Limit Infrastructure (core logic)

### Task 2.1: Implement tenant key function
- **File**: `backend/src/app/presentation/middleware/rate_limit.py`
- **Action**: Create `get_tenant_key(request: Request) -> str` that extracts `tenant_id` from JWT in Authorization header. Falls back to `get_remote_address(request)` if no valid JWT.
- **Spec**: REQ-RL-03, REQ-RL-05
- **Test**: Unit test with mock requests (with JWT, without JWT, with invalid JWT)
- [x] Done

### Task 2.2: Implement tier preload middleware
- **File**: `backend/src/app/presentation/middleware/rate_limit.py`
- **Action**: Create `TierPreloadMiddleware` (Starlette BaseHTTPMiddleware) that decodes JWT, resolves tier from TTLCache/DB, stores on `request.state.tier` AND in `_current_tier` ContextVar (for zero-arg slowapi callables). Uses `cachetools.TTLCache` with 60s TTL and 256 maxsize.
- **Spec**: REQ-RL-04, REQ-RL-07
- **Discovery**: slowapi limit callables MUST be zero-arg. ContextVar approach chosen over request.state for limit functions.
- [x] Done

### Task 2.3: Implement dynamic limit resolver functions
- **File**: `backend/src/app/presentation/middleware/rate_limit.py`
- **Action**: Create zero-arg `tier_limit_generate()`, `tier_limit_bulk()`, `tier_limit_refresh()` that read `_current_tier` ContextVar. Also `resolve_tier_limit_*` helpers for request-based testing.
- **Spec**: REQ-RL-04, REQ-RL-05
- [x] Done

### Task 2.4: Update Limiter initialization
- **File**: `backend/src/app/presentation/middleware/rate_limit.py`
- **Action**: Change `Limiter(key_func=get_remote_address)` to `Limiter(key_func=get_tenant_key)`
- **Spec**: REQ-RL-03
- [x] Done

### Task 2.5: Register tier preload middleware in main.py
- **File**: `backend/src/app/main.py`
- **Action**: Add `TierPreloadMiddleware` AFTER `SlowAPIMiddleware` (so it runs first as outer middleware in LIFO ordering).
- **Spec**: REQ-RL-04, REQ-RL-07
- [x] Done

## Phase 3: Endpoint Updates (wire it up)

### Task 3.1: Update auth.py rate limit decorators
- **File**: `backend/src/app/presentation/api/v1/auth.py`
- **Action**: 
  - Login: `@limiter.limit(lambda: get_settings().rate_limit_login, key_func=get_remote_address)` (explicit IP keying)
  - Refresh: `@limiter.limit(tier_limit_refresh)`
- **Spec**: REQ-RL-03, REQ-RL-04, ADR-5
- [x] Done

### Task 3.2: Update documents.py rate limit decorators
- **File**: `backend/src/app/presentation/api/v1/documents.py`
- **Action**:
  - Generate: `@limiter.limit(tier_limit_generate)`
  - Bulk: `@limiter.limit(tier_limit_bulk)`
- **Spec**: REQ-RL-04
- [x] Done

## Phase 4: API Schema Updates (expose to clients)

### Task 4.1: Update TierPublicSchema
- **File**: `backend/src/app/presentation/schemas/tier.py`
- **Action**: Add `rate_limit_login: str`, `rate_limit_refresh: str`, `rate_limit_generate: str`, `rate_limit_bulk: str` fields
- **Spec**: REQ-RL-06
- [x] Done

### Task 4.2: Update tiers.py list endpoint response mapping
- **File**: `backend/src/app/presentation/api/v1/tiers.py`
- **Action**: Include rate limit fields in `TierPublicSchema` construction in both `list_tiers` and `get_tenant_tier` endpoints
- **Spec**: REQ-RL-06, SC-RL-07, SC-RL-08
- [x] Done

## Phase 5: Tests (TDD — written alongside each phase)

### Task 5.1: Unit tests for rate limit resolver
- **File**: `backend/tests/unit/test_rate_limit_resolver.py` (new)
- **Action**: Test `get_tenant_key`, resolver helpers, ContextVar zero-arg callables
- **Spec**: REQ-RL-03, REQ-RL-04, REQ-RL-05
- [x] Done

### Task 5.2: Unit tests for SubscriptionTier entity defaults
- **File**: `backend/tests/unit/test_subscription_tier.py` (new)
- **Action**: Assert SubscriptionTier dataclass has correct default rate limit values
- **Spec**: REQ-RL-01
- [x] Done

### Task 5.3: Integration test — tier-specific rate limiting
- **File**: `backend/tests/integration/test_rate_limit.py` (extended)
- **Action**: SC-RL-01, SC-RL-03, SC-RL-05 tests. Used `_patch_limiter_dynamic_limit` helper to swap LimitGroup.__limit_provider at test time.
- **Spec**: SC-RL-01, SC-RL-03, SC-RL-05
- **Discovery**: slowapi stores callable by reference at decoration time. Only direct `LimitGroup._LimitGroup__limit_provider` patching works.
- [x] Done

### Task 5.4: Integration test — tiers API includes rate limits
- **File**: `backend/tests/integration/test_tiers_api.py` (extended)
- **Action**: SC-RL-07 (GET /tiers includes rate limits), SC-RL-08 (GET /tiers/tenant includes rate limits)
- **Spec**: SC-RL-07, SC-RL-08
- [x] Done

### Task 5.5: Verify all 231+ existing tests still pass
- **Action**: `pytest tests/ -x -q` → 264 passed (0 failures). Was 231 before, now 264 (+33 new tests).
- **Spec**: REQ-RL-08
- [x] Done

## Dependency Graph

```
Phase 1 (1.1, 1.2, 1.3, 1.4, 1.5) — all independent, can be done in parallel
    ↓
Phase 2 (2.1 → 2.2 → 2.3 → 2.4 → 2.5) — sequential, each builds on prior
    ↓
Phase 3 (3.1, 3.2) — parallel, depend on Phase 2
    ↓
Phase 4 (4.1 → 4.2) — sequential, depend on Phase 1
    ↓
Phase 5 (tests) — written alongside each phase (TDD), final pass at end
```

## Total: 16 tasks across 5 phases — ALL COMPLETE ✓
