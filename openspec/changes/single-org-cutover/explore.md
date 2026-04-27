# Exploration: single-org-cutover

**Goal:** Convert SigDoc's user-facing surface from multi-tenant SaaS to a single-organization system for CAINCO acquisition, keeping the multi-tenant schema intact under the hood while silencing or removing all SaaS-facing routes, components, and enforcement logic.

**Approach locked:** Nivel A — cosmetic SaaS removal. The multi-tenant DB schema is preserved. One tenant row, one tier row, all users in that singleton tenant. Only the surface changes.

---

## Current State

SigDoc ships as a multi-tenant SaaS product with:

### Frontend SaaS surface
- **`/signup` route** (`frontend/src/routes/signup.tsx`) — full self-service tenant + admin user creation form. Calls `POST /auth/signup`. Has a "¿Ya tiene cuenta? Inicie sesión" back-link.
- **`/subscription` route** (`frontend/src/routes/_authenticated/subscription/index.tsx`) — shows `TierCard` + `UsageWidget`. Active nav link in `_authenticated.tsx:59`.
- **`/usage` route** (`frontend/src/routes/_authenticated/usage/index.tsx`) — shows per-user + tenant usage stats. Active nav link in `_authenticated.tsx:53`.
- **`/verify-email` route** (`frontend/src/routes/verify-email.tsx`) — token verification landing page, calls `GET /auth/verify-email?token=`.
- **"Regístrese" link** on login page (`frontend/src/routes/login.tsx:87-92`) — a `<p>` block wrapping a `<Link to="/signup">` inside the LoginPage component.
- **`VerificationBanner`** (`frontend/src/features/users/components/VerificationBanner.tsx`) — rendered at `_authenticated.tsx:32` when `user.email_verified === false`. Calls `POST /auth/resend-verification`.
- **`QuotaExceededDialog`** (`frontend/src/features/subscription/components/QuotaExceededDialog.tsx`) — rendered at `_authenticated.tsx:91`. Listens for `"quota:exceeded"` `CustomEvent` on `window`.
- **Event dispatch** (`frontend/src/shared/lib/api-client.ts:36-40`) — on HTTP 429 with `error === "quota_exceeded"`, dispatches `new CustomEvent(QUOTA_EXCEEDED_EVENT, { detail: body })`.
- **`TierCard`** (`frontend/src/features/subscription/components/TierCard.tsx`) — tier badge with usage bars, calls `/api/v1/tiers/tenant`. Has a tier-slug conditional at line 133 that renders "¿Necesitás más recursos? Contactá al administrador…".
- **`UsageWidget`** (`frontend/src/features/usage/components/UsageWidget.tsx`) — used on both `/usage` and `/subscription` pages.
- **`TenantUsageTable`** (`frontend/src/features/usage/components/TenantUsageTable.tsx`) — admin-only usage breakdown, used on `/usage`.
- **`email_verified` field** in auth context (`frontend/src/shared/lib/auth.tsx:9`) — declared as `boolean` on the `User` interface. The `signup` method still lives in `AuthContextType` (line 16).

### Backend SaaS surface
- **`POST /auth/signup`** (`backend/src/app/presentation/api/v1/auth.py:42-91`) — creates new tenant + admin. Uses `SignupService`. Rate-limited via `settings.rate_limit_signup`.
- **`GET /auth/verify-email`** (`auth.py:256-277`) — verifies token, delegates to `EmailVerificationService.verify_token()`.
- **`POST /auth/resend-verification`** (`auth.py:280-317`) — resends verification email, delegates to `EmailVerificationService.resend_verification()`. Rate-limited 3/hour.
- **`SignupService`** (`backend/src/app/application/services/signup_service.py`) — atomic tenant + admin user creation. Step 7b sends verification email via `asyncio.create_task()`. 287 lines, self-contained.
- **`EmailVerificationService`** (`backend/src/app/application/services/email_verification_service.py`) — `send_verification`, `verify_token`, `resend_verification`. 165 lines.
- **`_require_verified_email` dependency** (`backend/src/app/presentation/api/v1/documents.py:47-68`) — called at `documents.py:85` (generate single) and `documents.py:170` (bulk generate). Loads user from DB, raises 403 if `email_verified is False`.
- **`/api/v1/tiers` router** (`backend/src/app/presentation/api/v1/tiers.py`) — two endpoints: `GET /tiers` (public, lists all active tiers) and `GET /tiers/tenant` (authenticated, returns tier + usage summary). Included in `main.py:73`.
- **`/api/v1/usage` router** (`backend/src/app/presentation/api/v1/usage.py`) — `GET /usage` (user stats, calls `QuotaService`) and `GET /usage/tenant` (admin-only). Included in `main.py:71`.
- **`QuotaService`** (`backend/src/app/application/services/quota_service.py`) — 233 lines, 6 public methods: `check_document_quota`, `check_template_limit`, `check_user_limit`, `check_bulk_limit`, `check_share_limit`, `get_usage_summary`. Called from:
  - `users.py:48` — `check_user_limit` on admin-create-user
  - `documents.py` — `check_document_quota` / `check_bulk_limit` in generate flows (via `get_document_service` DI)
  - `templates.py` — `check_template_limit` and `check_share_limit` in upload/share flows
  - `usage.py:63` — `get_tier_for_tenant` for enrichment
  - `tiers.py:93` — `get_tier_for_tenant` + `get_usage_summary`
- **`email_verified` column** (`backend/src/app/infrastructure/persistence/models/user.py:24`) — `Boolean, default=False, server_default="false"`. Also has `email_verification_token` and `email_verification_sent_at` columns (lines 25-28).
- **`/auth/forgot-password`** + **`/auth/reset-password`** (`auth.py:323-375`) — email-driven self-service password reset via `PasswordResetService`. **These are KEPT** — CAINCO decision pending (see Open Questions).
- **`TierPreloadMiddleware`** (`backend/src/app/presentation/middleware/rate_limit.py`) — decodes JWT, resolves tenant's tier from DB, stores on `request.state.tier`. Used by zero-arg rate-limit callables. **KEEP** — silencing quota does not affect rate limiting.
- **`QuotaExceededError` exception handler** (`main.py:23-35`, registered at `main.py:55`) — maps `QuotaExceededError` to HTTP 429. If quota is silenced, this handler becomes dormant but harmless. **KEEP**.
- **`_quota_exceeded_handler`** and its `app.add_exception_handler` call — dormant after QuotaService is silenced. No removal needed.
- **`admin-create-user` does NOT send a verification email** — `users.py:61-68` creates `UserModel` without calling `EmailVerificationService`. `email_verified` defaults to `False` at DB level. Post-cutover, this needs to default to `True` in the application layer (or the `_require_verified_email` check removed first).

### Test surface (directly affected)
Files that MUST be updated or deleted:

| File | Size | Why affected |
|------|------|--------------|
| `tests/integration/test_signup_api.py` | 236 lines | Entirely tests `POST /auth/signup` — route goes away |
| `tests/unit/test_signup_service.py` | 287 lines | Entirely tests `SignupService` — service kept but endpoint disabled; these tests are still valid unit tests for the service itself, but the integration tests become stale |
| `tests/unit/test_email_verification_service.py` | 208 lines | Entirely tests `EmailVerificationService` — service kept but no longer called |
| `tests/unit/test_quota_service.py` | 533 lines | Entirely tests `QuotaService` — service silenced; most tests become legacy |
| `tests/unit/test_usage_service.py` | ~file | Tests `UsageService` — used by `/usage` endpoint which gets router-disabled |
| `tests/integration/test_tiers_api.py` | 464 lines | Entirely tests `/tiers` endpoints — router disabled |
| `tests/integration/test_usage_api.py` | 216 lines | Tests `/usage` endpoints — router disabled |
| `tests/integration/test_auth_api.py` | partial | Lines 298-376 test `email_verified` in `/auth/me`; 401 tests for resend-verification |
| `tests/integration/test_documents_api.py` | partial | Lines 257-330 test `_require_verified_email` gate |
| `tests/integration/test_demo_reset_migration.py` | partial | Line 389-393 asserts `email_verified=True` in seed — still valid (seed behavior unchanged) |

**Estimated backend test delta:** 25-35 tests deleted or refactored out of the 565 passing baseline.

---

## Proposed Direction (Nivel A — Locked)

### REMOVE (delete files or disable routes)

**Frontend:**
- `frontend/src/routes/signup.tsx` — delete the file entirely (TanStack Router file-based: deleting the file removes the route)
- `frontend/src/routes/verify-email.tsx` — delete
- `frontend/src/routes/_authenticated/subscription/` directory — delete entire dir (2 files: `index.tsx` and implicit `__layout.tsx` if any)
- `frontend/src/routes/_authenticated/usage/` directory — delete entire dir
- `frontend/src/features/subscription/` directory — delete entire feature dir (6 files: `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `components/QuotaExceededDialog.tsx`, `components/TierCard.tsx`, `index.ts`)
- `frontend/src/features/usage/` directory — delete entire feature dir (6 files: `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `components/TenantUsageTable.tsx`, `components/UsageWidget.tsx`, `index.ts`)
- `frontend/src/features/users/components/VerificationBanner.tsx` — delete

**Frontend modifications:**
- `frontend/src/routes/login.tsx:87-92` — remove the `<p>` block ("¿No tiene cuenta? Regístrese")
- `frontend/src/routes/_authenticated.tsx` — remove: (a) `VerificationBanner` import + render at line 5 and 32, (b) `QuotaExceededDialog` import + render at lines 6 and 91, (c) `<Link to="/usage">` block (lines 52-58), (d) `<Link to="/subscription">` block (lines 59-65)
- `frontend/src/shared/lib/api-client.ts:1-3,36-40` — remove import of `QUOTA_EXCEEDED_EVENT` and the 429/quota dispatch block. The 401 redirect logic stays.
- `frontend/src/shared/lib/auth.tsx` — remove `email_verified: boolean` from `User` interface (line 9); remove `signup` method from `AuthContextType` (line 16) and its implementation (lines 45-64); remove `signup` from the context value (line 74)
- `frontend/src/features/users/index.ts` — remove `VerificationBanner` export

**Backend — disable router includes:**
- `backend/src/app/main.py:71` — remove `app.include_router(usage.router, ...)` line
- `backend/src/app/main.py:73` — remove `app.include_router(tiers.router, ...)` line
- `backend/src/app/main.py:12` — remove `usage, tiers` from the import line (keeps file clean)
- `backend/src/app/presentation/api/v1/auth.py:42-91` — remove the `signup` handler (the `@router.post("/signup")` function)
- `backend/src/app/presentation/api/v1/auth.py:256-317` — remove `verify_email` and `resend_verification` handlers
- `backend/src/app/presentation/api/v1/auth.py` imports — clean up unused: `EmailVerificationService`, `SignupService`, `SignupError`, `SignupRequest`, `SignupResponse`, `SignupUserResponse`
- `backend/src/app/presentation/api/v1/documents.py:47-68` — remove `_require_verified_email` function
- `backend/src/app/presentation/api/v1/documents.py:85` — remove `await _require_verified_email(current_user, session)` call
- `backend/src/app/presentation/api/v1/documents.py:170` — remove `await _require_verified_email(current_user, session)` call
- `backend/src/app/presentation/api/v1/documents.py` — remove `SQLAlchemyUserRepository` import if no longer used after removing `_require_verified_email`

**Backend — `email_verified` application layer:**
- `backend/src/app/presentation/api/v1/auth.py:209` — change `email_verified=getattr(user, "email_verified", True)` to always return `True` (or keep `getattr(user, "email_verified", True)` as-is — the default already handles unverified users gracefully, but existing users with `email_verified=False` in DB would still get `False` back via `/auth/me`). **Recommendation:** change line 209 to `email_verified=True` unconditionally to prevent the VerificationBanner from ever showing (belt-and-suspenders since the component is deleted from frontend anyway).
- `backend/src/app/domain/entities/user.py:19` — `email_verified: bool = False` — change default to `True` so newly admin-created users don't start unverified in the domain layer. No migration needed; we stop reading the field anyway.

### SILENCE (no-op, don't remove)

**`QuotaService`** (`backend/src/app/application/services/quota_service.py`):
- Add `_QUOTA_DISABLED: bool = True` constant at class level (or module level).
- Each of the five `check_*` methods gets an early return:
  ```python
  if _QUOTA_DISABLED:
      return
  ```
- `get_usage_summary` returns a "no limits" stub when disabled:
  ```python
  if _QUOTA_DISABLED:
      return {"tier": {"id": "N/A", "name": "Unlimited", "slug": "unlimited"}, "documents": ..., ...}
  ```
- `get_tier_for_tenant` stays as-is (still needed by `TierPreloadMiddleware` and rate limiting).
- This approach: (a) keeps all existing DI wiring, (b) existing tests that call `check_*` still pass if they don't mock the constant, (c) easy to flip for Nivel B.

### KEEP (no change)

- Multi-tenant DB schema: `tenants`, `subscription_tiers`, `usage_events`, `rate_limits` tables
- `TenantMiddleware` and `TierPreloadMiddleware` — rate limiting still works per-tier
- `QuotaExceededError` exception class + `_quota_exceeded_handler` in `main.py` — dormant but harmless
- `PasswordResetService` + `/auth/forgot-password` + `/auth/reset-password` + `frontend/src/routes/forgot-password.tsx` + `frontend/src/routes/reset-password.tsx` — pending explicit decision (see Open Questions)
- 3-role taxonomy (admin, template_creator, document_generator)
- Audit log — `AuditAction.AUTH_SIGNUP` stays in the enum even if unused
- Admin password reset feature (cc71902)
- Dev recovery endpoint (8330b13) — still gated by `settings.enable_dev_reset`
- Templates + PDF flow
- All role-aware UI (split-button in documents page, admin-only nav links for Users and Audit)
- `email_verified` column in DB (Nivel B cleanup)
- `email_verification_token`, `email_verification_sent_at`, `password_reset_token`, `password_reset_sent_at` columns (Nivel B cleanup)

---

## Module Map

### Frontend

| File | Action | Notes |
|------|--------|-------|
| `frontend/src/routes/signup.tsx` | **[REMOVE]** | Delete file; route auto-removed |
| `frontend/src/routes/verify-email.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/routes/_authenticated/subscription/index.tsx` | **[REMOVE]** | Delete file + dir |
| `frontend/src/routes/_authenticated/usage/index.tsx` | **[REMOVE]** | Delete file + dir |
| `frontend/src/features/subscription/components/QuotaExceededDialog.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/features/subscription/components/TierCard.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/features/subscription/api/index.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/subscription/api/keys.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/subscription/api/queries.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/subscription/index.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/components/UsageWidget.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/components/TenantUsageTable.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/api/index.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/api/keys.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/api/queries.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/usage/index.ts` | **[REMOVE]** | Delete file |
| `frontend/src/features/users/components/VerificationBanner.tsx` | **[REMOVE]** | Delete file |
| `frontend/src/routes/login.tsx` | **[MODIFY]** | Remove lines 87-92 (`<p>¿No tiene cuenta?...`) |
| `frontend/src/routes/_authenticated.tsx` | **[MODIFY]** | Remove VerificationBanner + QuotaExceededDialog imports/renders; remove `/usage` and `/subscription` nav links |
| `frontend/src/shared/lib/api-client.ts` | **[MODIFY]** | Remove QUOTA_EXCEEDED_EVENT import (line 2) and quota dispatch block (lines 36-40) |
| `frontend/src/shared/lib/auth.tsx` | **[MODIFY]** | Remove `email_verified` field, `signup` method, and `signup` implementation |
| `frontend/src/features/users/index.ts` | **[MODIFY]** | Remove `VerificationBanner` export |
| `frontend/src/routes/forgot-password.tsx` | **[NO CHANGE]** | Pending decision |
| `frontend/src/routes/reset-password.tsx` | **[NO CHANGE]** | Pending decision |
| `frontend/src/routes/_authenticated/users/index.tsx` | **[NO CHANGE]** | |
| `frontend/src/routes/_authenticated/templates/` | **[NO CHANGE]** | |
| `frontend/src/routes/_authenticated/documents/` | **[NO CHANGE]** | |
| `frontend/src/routes/_authenticated/audit/index.tsx` | **[NO CHANGE]** | |

### Backend

| File | Action | Notes |
|------|--------|-------|
| `backend/src/app/main.py` | **[MODIFY]** | Remove `usage` and `tiers` router includes (lines 71, 73); clean import line 12 |
| `backend/src/app/presentation/api/v1/auth.py` | **[MODIFY]** | Remove `signup` handler (lines 42-91), `verify_email` handler (lines 256-277), `resend_verification` handler (lines 280-317); clean up unused imports; change line 209 `email_verified=True` |
| `backend/src/app/presentation/api/v1/documents.py` | **[MODIFY]** | Remove `_require_verified_email` function (lines 47-68) and its two call sites (lines 85, 170); remove `SQLAlchemyUserRepository` import if unused |
| `backend/src/app/application/services/quota_service.py` | **[MODIFY]** | Add `_QUOTA_DISABLED = True` flag; early-return in all `check_*` methods; stub `get_usage_summary` when disabled |
| `backend/src/app/domain/entities/user.py` | **[MODIFY]** | Change `email_verified: bool = False` → `email_verified: bool = True` |
| `backend/src/app/presentation/api/v1/usage.py` | **[NO CHANGE]** | File kept; just router not included |
| `backend/src/app/presentation/api/v1/tiers.py` | **[NO CHANGE]** | File kept; just router not included |
| `backend/src/app/application/services/signup_service.py` | **[NO CHANGE]** | File kept; endpoint removed, service class stays |
| `backend/src/app/application/services/email_verification_service.py` | **[NO CHANGE]** | File kept; endpoints removed, service stays |
| `backend/src/app/presentation/middleware/rate_limit.py` | **[NO CHANGE]** | TierPreloadMiddleware still active |
| `backend/src/app/presentation/middleware/tenant.py` | **[NO CHANGE]** | |
| `backend/src/app/domain/entities/user.py` | **[MODIFY]** | See above |
| `backend/src/app/infrastructure/persistence/models/user.py` | **[NO CHANGE]** | Columns stay; Nivel B drops them |
| `backend/src/app/presentation/api/v1/users.py` | **[MODIFY]** | Remove `quota_service.check_user_limit` call (lines 38-51); remove `get_quota_service` import and `QuotaService` dependency from `create_user` handler |
| `backend/src/app/presentation/schemas/auth.py` | **[MODIFY]** | Remove `SignupRequest`, `SignupResponse`, `SignupUserResponse` schemas; keep `UserResponse.email_verified` field (used in `/auth/me` response, now always `True`) |

### Backend Tests

| File | Action | Notes |
|------|--------|-------|
| `tests/integration/test_signup_api.py` | **[REMOVE]** | All tests become stale (endpoint 404s) |
| `tests/unit/test_signup_service.py` | **[NO CHANGE]** | Service still exists; unit tests remain valid |
| `tests/unit/test_email_verification_service.py` | **[NO CHANGE]** | Service still exists; tests still valid |
| `tests/unit/test_quota_service.py` | **[MODIFY]** | Add tests asserting `_QUOTA_DISABLED=True` short-circuits all `check_*` methods; existing tests may need `_QUOTA_DISABLED=False` override |
| `tests/integration/test_tiers_api.py` | **[REMOVE]** | Router disabled; all 464 lines become 404 tests |
| `tests/integration/test_usage_api.py` | **[REMOVE]** | Router disabled |
| `tests/integration/test_auth_api.py` | **[MODIFY]** | Remove `email_verified` assertions at lines 302-327; remove test at line 376; remove any signup-related stubs |
| `tests/integration/test_documents_api.py` | **[MODIFY]** | Remove T-VERIFY-15 block (lines 257-330, the `_require_verified_email` tests) |
| `tests/integration/test_users_api.py` | **[MODIFY]** | Remove quota mock setup for `create_user`; test still passes after quota is silenced (no-op) |
| `tests/unit/test_usage_service.py` | **[NO CHANGE]** | `UsageService` itself is kept; unit tests remain valid |

---

## Tradeoffs

### T1: Disable `/auth/signup` (router exclusion) vs delete (remove handler)
**Chosen: remove handler** (`[MODIFY]` auth.py — delete the function body and its imports).
- Removing the function body from `auth.py` is the Nivel A sweet spot: the `SignupService` class is still there for reference; the handler code is gone so there's no dead endpoint that could accidentally be re-enabled by a stray router include. Router exclusion alone leaves 80 lines of dead code that someone might mistakenly uncomment.
- Verdict: **remove the handler, keep the service class** for Nivel B reference.

### T2: Drop `email_verified` column vs leave it
**Chosen: leave column, stop reading it** (Nivel A).
- Migration head stays at `012_demo_reset`. Zero DB changes in this batch.
- The column value is irrelevant once `_require_verified_email` is removed from documents endpoints. The `/auth/me` response can hard-code `email_verified: true` in the application layer.
- Verdict: **Nivel B drops the column** via migration `013`.

### T3: Silence `QuotaService` vs remove it
**Chosen: silence** (add `_QUOTA_DISABLED = True` flag, early-return in all `check_*` methods).
- Endpoints still wire up `QuotaService` via DI. Existing tests that mock `fake_quota_service` still compile. Nivel B flips the flag to `False` and removes the class.
- The `get_tier_for_tenant` method must stay live because `TierPreloadMiddleware` needs it for rate-limit tier resolution.
- Verdict: **silence all `check_*` and `get_usage_summary`; keep `get_tier_for_tenant` active**.

### T4: `/subscription` and `/usage` — disable backend router or leave it?
**Chosen: disable backend router** (remove `include_router` calls in `main.py`) AND delete frontend routes.
- The endpoints return 404 without frontend access and without router includes, reducing attack surface.
- The source files are preserved for Nivel B (where they get deleted entirely alongside the tables they read from).
- Verdict: **remove router includes + delete frontend directories**.

### T5: Email-driven forgot-password/reset-password — keep or remove?
**Unresolved — Open Question (see below).**
- The admin-driven password reset (cc71902) covers the case where an admin resets another user's password.
- Self-service "I forgot my password" via email (`/auth/forgot-password`) is a separate user experience.
- CAINCO may want this for standalone users who forget their password without bothering IT.
- **Recommendation: KEEP for now** (both the frontend routes and backend handlers), pending explicit CAINCO confirmation.

---

## Open Questions for the Proposal Phase

1. **`email_verified` column default going forward**: After this change, `email_verified` stays in the DB with whatever value it has. Newly admin-created users get `email_verified=False` at the DB level (model default is still `false`). We should change `domain/entities/user.py` default to `True` and also consider whether we want to backfill existing users to `True` (one-liner SQL, no migration needed if done in `dev.py` reset or as a seed). **Recommendation: change domain default to `True`; leave existing rows as-is (we stop reading the field).**

2. **Self-service forgot-password / reset-password via email**: Does CAINCO want users to be able to reset their own password via email link? Or is all password management admin-driven? This affects whether we keep `frontend/src/routes/forgot-password.tsx`, `frontend/src/routes/reset-password.tsx`, `backend/.../auth.py` `/forgot-password` and `/reset-password` handlers, and `PasswordResetService`. **Recommend: keep until explicitly told to remove.**

3. **Unused tier/usage_events tables**: These stay for Nivel B. No questions here — confirmed deferred.

4. **`UsageWidget` referenced in both `/subscription` and `/usage` routes**: The `/subscription` page also embeds `UsageWidget`. Since both routes are being removed simultaneously, no orphan component issue. Confirmed: delete the whole `features/usage/` directory.

5. **`signup` method in `AuthContextType`**: The `signup` callback in `auth.tsx` calls `POST /auth/signup`. When the endpoint returns 404, the frontend `signup` method would error. Removing the method + the `signup.tsx` route simultaneously means no UI path can call it. But the `AuthContextType` interface still exports `signup` which could be confusing. **Recommendation: remove the `signup` method from `auth.tsx` entirely** — it's dead code once the endpoint and route are gone.

---

## Risks

1. **TypeScript compilation errors from import chain**: Removing `features/subscription/` and `features/usage/` directories will break any file that imports from them. Known dependents: `_authenticated.tsx` (imports `QuotaExceededDialog`, `VerificationBanner`), `api-client.ts` (imports `QUOTA_EXCEEDED_EVENT`), subscription route (imports `TierCard`, `UsageWidget`), usage route (imports `UsageWidget`, `TenantUsageTable`). All these files are themselves being modified or removed — the entire import chain is within the removal scope. **Risk: LOW if all deletions happen atomically in the same PR.**

2. **`fake_quota_service.py` in tests**: `tests/fakes/fake_quota_service.py` exists and is imported in many integration test conftest fixtures. After silencing `QuotaService`, the fake is still wired in, but calls are no-ops. This is fine — the fake can remain as-is. **Risk: LOW.**

3. **`create_user` in `users.py` calls `quota_service.check_user_limit`**: After silencing, this call becomes a no-op. But the DI still injects `QuotaService`. This is fine for Nivel A. **Alternative: remove the dependency injection from `create_user` entirely in Nivel A** — cleaner but touches more test fixtures. **Recommendation: leave the DI wiring; quota is silenced at service level.** Risk: LOW.

4. **Existing users with `email_verified=False` in DB**: On the demo VPS, the seeded admin has `email_verified=True` (per migration 012 seed). But any users created by admin via `/users` POST will have `email_verified=False` (DB default). Once `_require_verified_email` is removed from documents, those users can generate documents fine. But `/auth/me` would return `email_verified: false` for them, which — since `VerificationBanner` is deleted from frontend — is invisible. However, if we hard-code `email_verified: true` in `auth.py:/auth/me`, this risk disappears entirely. **Recommendation: hard-code `True` in `/auth/me` response.** Risk: LOW if done.

5. **`TierPreloadMiddleware` reads tier from DB for rate limiting**: If `QuotaService` silencing accidentally breaks the tier resolution path, rate limits could fall back to defaults. Specifically: `get_tier_for_tenant` in `QuotaService` must NOT be silenced, only the `check_*` methods. **Risk: LOW if the silencing is applied only to `check_*` and `get_usage_summary`.**

6. **`AuditAction.AUTH_SIGNUP` enum value becomes unused**: The enum entry stays, no harm. Tests that assert signup audit events will be deleted with `test_signup_api.py`. **Risk: NONE.**

7. **Test count regression**: Removing 25-35 tests drops the baseline below 565. The proposal should document the new expected baseline. Per TDD protocol, we don't add NEW tests for removed code; we update/delete stale tests. **Risk: acceptable — must be documented in the spec phase.**

---

## Files Read

| File | What I learned |
|------|---------------|
| `backend/src/app/main.py` | Router includes for `usage` (line 71) and `tiers` (line 73) are the exact two lines to remove; `_quota_exceeded_handler` registered at line 55 |
| `backend/src/app/presentation/api/v1/auth.py` | `signup` handler is lines 42-91; `verify_email` is 256-277; `resend_verification` is 280-317; `/auth/me` has `email_verified=getattr(user, "email_verified", True)` at line 209 |
| `backend/src/app/application/services/quota_service.py` | 6 public methods: 5 `check_*` + `get_usage_summary`; `get_tier_for_tenant` must stay live for middleware; 233 lines |
| `backend/src/app/application/services/signup_service.py` | Step 7b sends verification email via `asyncio.create_task()`; no email sent in admin-create-user path |
| `backend/src/app/application/services/email_verification_service.py` | `send_verification`, `verify_token`, `resend_verification` — all in one class; 165 lines |
| `backend/src/app/presentation/api/v1/documents.py` | `_require_verified_email` at lines 47-68; called at lines 85 and 170 (single + bulk generate) |
| `backend/src/app/presentation/api/v1/users.py` | `create_user` calls `quota_service.check_user_limit` at line 48; does NOT send verification email |
| `backend/src/app/presentation/api/v1/usage.py` | Two endpoints: user usage (calls `QuotaService` for enrichment) and admin tenant usage |
| `backend/src/app/presentation/api/v1/tiers.py` | Two endpoints: public `GET /tiers` and authenticated `GET /tiers/tenant`; both call `QuotaService` |
| `backend/src/app/infrastructure/persistence/models/user.py` | `email_verified` column at line 24 with `default=False, server_default="false"`; verification token columns at 25-28 |
| `backend/src/app/domain/entities/user.py` | Domain entity `email_verified: bool = False` at line 19 — needs to change to `True` |
| `backend/src/app/presentation/api/dependencies.py` | No email_verified dependency here; `_require_verified_email` is local to `documents.py` |
| `frontend/src/routes/login.tsx` | "¿No tiene cuenta? Regístrese" block at lines 87-92 |
| `frontend/src/routes/_authenticated.tsx` | `VerificationBanner` import + conditional render at line 32; `QuotaExceededDialog` render at line 91; `/usage` nav link at 52-58; `/subscription` nav link at 59-65 |
| `frontend/src/shared/lib/api-client.ts` | `QUOTA_EXCEEDED_EVENT` import at line 2; quota dispatch block at lines 36-40 |
| `frontend/src/shared/lib/auth.tsx` | `email_verified: boolean` in User interface at line 9; `signup` method in context at line 16 and implementation at lines 45-64 |
| `frontend/src/features/subscription/components/QuotaExceededDialog.tsx` | Listens for `"quota:exceeded"` CustomEvent via `window.addEventListener`; rendered in `_authenticated.tsx` layout |
| `frontend/src/features/subscription/components/TierCard.tsx` | Has tier-slug conditional at line 133 (tier badge) — entire file removed |
| `frontend/src/features/users/components/VerificationBanner.tsx` | Calls `POST /auth/resend-verification`; 39 lines |
| `tests/integration/test_signup_api.py` | 236 lines, entirely tests `POST /auth/signup`; all stale |
| `tests/integration/test_tiers_api.py` | 464 lines; entirely tests `/tiers` endpoints |
| `tests/integration/test_usage_api.py` | 216 lines; tests `/usage` endpoints |
| `tests/unit/test_quota_service.py` | 533 lines; tests all `check_*` methods |
| `tests/unit/test_email_verification_service.py` | 208 lines; tests `EmailVerificationService` |
| `openspec/` | Exists; `changes/` directory confirmed; `single-org-cutover/` dir did not exist (created by this exploration) |

---

## Ready for Proposal

**Yes.** The direction is fully locked (Nivel A). The proposal phase needs to:
1. Confirm the two open questions (forgot-password email flow; email_verified backfill strategy)
2. Formally record the "silence QuotaService" ADR
3. State the new expected test count baseline after deletions
4. Confirm migration head stays at 012 (no DB changes in this batch)
