# Tasks: Self-Service Tenant Onboarding

**Change**: `tenant-onboarding`
**Status**: in-progress (backend complete, frontend pending)
**Date**: 2026-04-07
**Total tasks**: 18
**Strict TDD**: Yes — tests written BEFORE implementation for all tasks

---

## Phase 1: Domain & Infrastructure Foundation

### Task 1.1: TenantRepository Port
**File**: `backend/src/app/domain/ports/tenant_repository.py` (NEW)
**Test**: `backend/tests/unit/test_tenant_repository_port.py`
- [x] Define abstract `TenantRepository` class with methods:
  - `create(tenant: TenantModel) -> TenantModel`
  - `get_by_name(name: str) -> TenantModel | None` (case-insensitive)
  - `get_by_slug(slug: str) -> TenantModel | None`
- [x] Write test verifying the ABC cannot be instantiated directly

### Task 1.2: FakeTenantRepository
**File**: `backend/tests/fakes/fake_tenant_repository.py` (NEW)
**Modify**: `backend/tests/fakes/__init__.py`
- [x] Implement in-memory `FakeTenantRepository` implementing `TenantRepository`
- [x] Dict-backed storage with secondary indexes on name (lowered) and slug
- [x] Export from `tests/fakes/__init__.py`
- [x] Write tests verifying CRUD operations

### Task 1.3: SQLAlchemy TenantRepository
**File**: `backend/src/app/infrastructure/persistence/repositories/tenant_repository.py` (NEW)
**Test**: `backend/tests/unit/test_tenant_repository_sqlalchemy.py`
- [x] Implement `SQLAlchemyTenantRepository(session)` 
- [x] `get_by_name`: exact match on name column
- [x] `get_by_slug`: exact match on slug column
- [x] `create`: add + flush (same pattern as `SQLAlchemyUserRepository.create`)

### Task 1.4: Add AUTH_SIGNUP Audit Action
**File**: `backend/src/app/domain/entities/audit_log.py` (MODIFY)
**Test**: `backend/tests/unit/test_audit_action.py`
- [x] Add `AUTH_SIGNUP = "auth.signup"` to `AuditAction` class
- [x] Write test verifying the constant value

---

## Phase 2: Slug Utility

### Task 2.1: Slug Generation Functions
**File**: `backend/src/app/application/services/slug_utils.py` (NEW)
**Test**: `backend/tests/unit/test_slug_utils.py`
- [x] `slugify(name: str) -> str` — lowercase, replace non-alnum with hyphens, collapse, strip
- [x] `unique_slug(base: str, exists_fn) -> str` — checks existence via async callable, appends `-N` suffix if collision
- [x] Write tests for:
  - Basic slugification: "Acme Corp" → "acme-corp"
  - Special characters: "My Org!!!" → "my-org"
  - Unicode: "Héllo Wörld" → "hello-world"
  - Consecutive hyphens: "foo--bar" → "foo-bar"
  - Leading/trailing: "-foo-" → "foo"
  - Collision dedup: existing "acme" → "acme-2", "acme-3", "acme-4"

---

## Phase 3: Signup Service (Application Layer)

### Task 3.1: SignupRequest Schema
**File**: `backend/src/app/presentation/schemas/auth.py` (MODIFY)
**Test**: `backend/tests/unit/test_auth_schemas.py`
- [x] Add `SignupRequest` pydantic model:
  - `email: str` (with regex validator — pydantic[email] not installed)
  - `password: str` (validator: min_length=8)
  - `full_name: str` (validator: not empty)
  - `organization_name: str` (validator: not empty)
- [x] Add `SignupResponse` and `SignupUserResponse` schemas

### Task 3.2: SignupService
**File**: `backend/src/app/application/services/signup_service.py` (NEW)
**Test**: `backend/tests/unit/test_signup_service.py`
- [x] `SignupService.__init__(self, tenant_repo, user_repo, tier_repo, audit_service)` — receives repos via DI
- [x] `signup(email, password, full_name, org_name, ip_address) -> SignupResult`:
  1. Check email uniqueness → raise SignupError(field="email") if exists
  2. Check org name uniqueness → raise SignupError(field="organization_name") if exists
  3. Generate unique slug via `unique_slug(base, async_exists_fn)`
  4. Resolve Free tier via `tier_repo.get_by_slug("free")` with FREE_TIER_ID fallback
  5. Create Tenant
  6. Create User (admin role, hashed password)
  7. Fire-and-forget audit log
  8. Return SignupResult with JWT tokens
- [x] Write unit tests using fakes (9 tests, all passing)

### Task 3.3: Settings — rate_limit_signup
**File**: `backend/src/app/config.py` (MODIFY)
- [x] Add `rate_limit_signup: str = "3/hour"` to `Settings`

---

## Phase 4: API Endpoint

### Task 4.1: POST /auth/signup Endpoint
**File**: `backend/src/app/presentation/api/v1/auth.py` (MODIFY)
**Test**: `backend/tests/integration/test_signup_api.py`
- [x] Add `@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)`
- [x] Rate limit: `@limiter.limit(lambda: get_settings().rate_limit_signup, key_func=get_remote_address)`
- [x] Handler logic:
  1. Create repos + SignupService(tenant_repo, user_repo, tier_repo, audit_service)
  2. Call `service.signup(email, password, full_name, org_name, ip_address)`
  3. Catch `SignupError` → 409
  4. Return SignupResponse with tokens + user info
- [x] Write integration tests (7 tests: happy path, 409×2, 422×3, 429×1 — all passing)

---

## Phase 5: Database Migration

### Task 5.1: Alembic Migration 007
**File**: `backend/alembic/versions/007_tenant_onboarding.py` (NEW)
- [x] Add unique index `uq_users_email_global` on `users.email` (global, not per-tenant)
- [x] Add unique constraint `uq_tenants_name` on `tenants.name`
- [x] Downgrade: drop constraint + index

---

## Phase 6: Frontend

### Task 6.1: Auth Context — signup Method
**File**: `frontend/src/shared/lib/auth.tsx` (MODIFY)
- [x] Add `signup` to `AuthContextType` interface
- [x] Implement `signup` in `AuthProvider`: POST `/auth/signup`, store tokens, fetch `/auth/me`
- [x] Update `AuthContext.Provider` value to include `signup`

### Task 6.2: Signup Page
**File**: `frontend/src/routes/signup.tsx` (NEW)
- [x] Create public route at `/signup` using `createFileRoute`
- [x] Form fields: email, password, full_name, organization_name
- [x] Client validation: required fields, password min 8 chars
- [x] On submit: call `signup(...)`, redirect to `/templates`, toast "¡Bienvenido a SigDoc!"
- [x] Error handling:
  - 409 → extract detail from response, show as error toast
  - 429 → toast "Demasiados intentos. Intente más tarde"
  - Other → toast "Error al registrarse"
- [x] Redirect to `/templates` if already authenticated (same pattern as login)
- [x] Link to `/login`: "¿Ya tiene cuenta? Inicie sesión"

### Task 6.3: Login Page — Signup Link
**File**: `frontend/src/routes/login.tsx` (MODIFY)
- [x] Add link below the login button: "¿No tiene cuenta? Regístrese" → `/signup`
- [x] Use `<Link>` from `@tanstack/react-router`

---

## Phase 7: Verification & Cleanup

### Task 7.1: Full Test Suite Run
- [x] Run all backend tests — 295 passed (264 existing + 31 new), 0 failures
- [x] Run all new tests — 31 new tests, all pass
- [x] Count total tests: 295

### Task 7.2: Manual Smoke Test
- [ ] Start dev environment
- [ ] Navigate to `/signup`
- [ ] Complete signup flow end-to-end
- [ ] Verify redirect to `/templates` with welcome toast
- [ ] Verify login with new credentials works
- [ ] Verify duplicate email/org returns error

---

## Dependency Graph

```
1.1 (port) ──┬──→ 1.2 (fake) ──→ 3.2 (service) ──→ 4.1 (endpoint)
             │                                          │
             └──→ 1.3 (sqlalchemy repo)                │
                                                        │
1.4 (audit action) ─────────────────────────────────→ 4.1
                                                        │
2.1 (slug utils) ─────→ 3.2 (service)                  │
                                                        │
3.1 (schema) ──────────→ 4.1 (endpoint)                │
                                                        │
3.3 (settings) ────────→ 4.1 (endpoint)                │
                                                        │
5.1 (migration) ───────────────────────────── (parallel, no code deps)
                                                        │
                        6.1 (auth context) ──→ 6.2 (signup page)
                                                        │
                        6.3 (login link) ──── (parallel)│
                                                        │
                                              7.1 (test run) → 7.2 (smoke)
```

## Execution Order (Batches)

| Batch | Tasks | Can Parallelize |
|-------|-------|----------------|
| 1 | 1.1, 1.4, 2.1, 3.1, 3.3 | Yes — all independent |
| 2 | 1.2, 1.3 | Yes — both depend only on 1.1 |
| 3 | 3.2 | No — depends on 1.2, 2.1 |
| 4 | 4.1, 5.1 | Yes — endpoint + migration are independent |
| 5 | 6.1, 6.3 | Yes — auth context + login link are independent |
| 6 | 6.2 | No — depends on 6.1 |
| 7 | 7.1, 7.2 | Sequential |
