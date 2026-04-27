# Tasks — single-org-cutover

## Conventions
- Strict TDD where applicable: for removals, update/delete stale tests; for new behavior, write failing test first.
- Task IDs: `T-<PHASE>-<NN>`. DONE when code matches spec, related tests pass, no regressions.
- Phases 1-3 are backend. Phases 4-5 are frontend (must land atomically together). Phase 6 cleans tests. Phase 7 is the verification gate.
- Migration head stays at `012` — NO schema changes.

---

## Phase 1 — Backend route disabling

### [x] T-1-01: Remove signup/verify-email/resend-verification handlers from auth.py
- **Files**: `backend/src/app/presentation/api/v1/auth.py`
- **REQs**: REQ-SOS-01, REQ-SOS-02 / D-01
- **Depends on**: —
- **Description**: Delete the `signup` handler (lines 42-91), `verify_email` handler (lines 256-277), and `resend_verification` handler (lines 280-317). Clean unused imports (`EmailVerificationService`, `SignupService`, `SignupError`, `SignupRequest`, `SignupResponse`, `SignupUserResponse`).

### [x] T-1-02: Remove forgot-password/reset-password handlers from auth.py
- **Files**: `backend/src/app/presentation/api/v1/auth.py`
- **REQs**: REQ-SOS-02 / D-01
- **Depends on**: T-1-01
- **Description**: Delete the `forgot_password` and `reset_password` handler functions (lines ~323-375). Clean any `PasswordResetService` import that becomes unused in this file.

### [x] T-1-03: Remove tiers and usage router includes from main.py
- **Files**: `backend/src/app/main.py`
- **REQs**: REQ-SOS-03 / D-01
- **Depends on**: —
- **Description**: Remove lines 71 (`app.include_router(usage.router, ...)`) and 73 (`app.include_router(tiers.router, ...)`). Remove `usage, tiers` from the import on line 12.

### [x] T-1-04: Add DEPRECATED docstrings to kept service files
- **Files**: `backend/src/app/application/services/signup_service.py`, `email_verification_service.py`, `password_reset_service.py`
- **REQs**: REQ-SOS-20 / D-11
- **Depends on**: —
- **Description**: Add module-level `"""DEPRECATED: route disabled per single-org-cutover; remove in Nivel B."""` to each of the three service files.

---

## Phase 2 — Backend QuotaService silencing

### [x] T-2-01: [RED] Write failing tests for _QUOTA_DISABLED default behavior
- **Files**: `backend/tests/unit/test_quota_service.py`
- **REQs**: REQ-QSI-01 through REQ-QSI-07, REQ-QSI-11 / D-04
- **Depends on**: —
- **Description**: Add tests asserting: (a) with default `_QUOTA_DISABLED=True`, each of the 5 `check_*` methods returns without raising; (b) `get_usage_summary` returns a no-limits stub (limit=None); (c) `get_tier_for_tenant` is NOT affected (still queries DB); (d) overriding `_QUOTA_DISABLED=False` on the instance causes `check_document_quota` to raise `QuotaExceededError` when over limit (SCEN-QSI-05). Existing tests that test enforcement must set `_QUOTA_DISABLED=False` on the instance — add that override.

### [x] T-2-02: [GREEN] Implement _QUOTA_DISABLED flag in QuotaService
- **Files**: `backend/src/app/application/services/quota_service.py`
- **REQs**: REQ-QSI-01 through REQ-QSI-08 / D-04
- **Depends on**: T-2-01
- **Description**: Add `_QUOTA_DISABLED: bool = True` class constant. Add early-return guard `if self._QUOTA_DISABLED: return` (or stub) to `check_document_quota`, `check_template_limit`, `check_user_limit`, `check_bulk_limit`, `check_share_limit`. For `get_usage_summary`, return a `{"limit": None, ...}` stub per resource. Leave `get_tier_for_tenant` completely untouched. Add class-level docstring noting the flag and referencing the cutover.

---

## Phase 3 — Backend documents.py, users.py, auth/me, and domain entity

### T-3-01: [RED] Test that email_verified=False user can generate documents
- **Files**: `backend/tests/integration/test_documents_api.py`
- **REQs**: REQ-SOS-13 / D-02
- **Depends on**: —
- **Description**: Remove the existing `_require_verified_email` test block (lines 257-330, T-VERIFY-15). Add a test asserting a user with `email_verified=False` in DB can call `POST /api/v1/documents/generate` and get 200/202 (no 403).

### T-3-02: [GREEN] Remove _require_verified_email from documents.py
- **Files**: `backend/src/app/presentation/api/v1/documents.py`
- **REQs**: REQ-SOS-13 / D-02
- **Depends on**: T-3-01
- **Description**: Delete the `_require_verified_email` function (lines 47-68) and its two `Depends(...)` call sites (lines 85 and 170). Remove `SQLAlchemyUserRepository` import if it becomes unused after this removal.

### T-3-03: Remove quota_service.check_user_limit call from users.py
- **Files**: `backend/src/app/presentation/api/v1/users.py`
- **REQs**: REQ-QSI-10, REQ-SOS-19 / D-04
- **Depends on**: T-2-02
- **Description**: Remove the `quota_service.check_user_limit` call (lines 38-51 area) from `create_user`. The `QuotaService` DI stays wired (silenced at service level) — only remove the explicit `check_user_limit` call from the handler. Also verify no `EmailVerificationService` call exists in this handler (SCEN-SOS-11).

### T-3-04: [RED] Test /auth/me returns email_verified true despite DB false
- **Files**: `backend/tests/integration/test_auth_api.py`
- **REQs**: REQ-SOS-14 / D-03
- **Depends on**: —
- **Description**: Remove existing test assertions that expect `email_verified` to reflect DB value (lines 302-327). Add a test asserting `/auth/me` returns `email_verified: true` for a user whose DB row has `email_verified=False`.

### T-3-05: [GREEN] Hardcode email_verified=True in /auth/me response and domain entity
- **Files**: `backend/src/app/presentation/api/v1/auth.py`, `backend/src/app/domain/entities/user.py`
- **REQs**: REQ-SOS-14, REQ-SOS-15 / D-03
- **Depends on**: T-3-04
- **Description**: In `auth.py` line 209, change to `email_verified=True` unconditionally. In `user.py` line 19, change `email_verified: bool = False` to `email_verified: bool = True`.

### T-3-06: Drop SignupRequest/SignupResponse/SignupUserResponse from auth schemas
- **Files**: `backend/src/app/presentation/schemas/auth.py`
- **REQs**: REQ-SOS-01 / D-01
- **Depends on**: T-1-01
- **Description**: Remove `SignupRequest`, `SignupResponse`, `SignupUserResponse` schema classes. Keep `UserResponse` with its `email_verified` field intact (it's still used in `/auth/me`).

---

## Phase 4 — Frontend deletions (atomic — all deletions must land with Phase 5)

### T-4-01: Delete features/subscription/ directory (6 files)
- **Files**: `frontend/src/features/subscription/` (all 6 files: `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `components/QuotaExceededDialog.tsx`, `components/TierCard.tsx`, `index.ts`)
- **REQs**: REQ-SOS-11 / D-05
- **Depends on**: Phase 5 must land in same commit
- **Description**: Delete the entire `features/subscription/` directory. This will break TypeScript until Phase 5 removes all consumers.

### T-4-02: Delete features/usage/ directory (6 files)
- **Files**: `frontend/src/features/usage/` (all 6 files: `api/index.ts`, `api/keys.ts`, `api/queries.ts`, `components/TenantUsageTable.tsx`, `components/UsageWidget.tsx`, `index.ts`)
- **REQs**: REQ-SOS-12 / D-05
- **Depends on**: Phase 5 must land in same commit
- **Description**: Delete the entire `features/usage/` directory.

### T-4-03: Delete frontend route files (signup, verify-email, forgot-password, reset-password)
- **Files**: `frontend/src/routes/signup.tsx`, `frontend/src/routes/verify-email.tsx`, `frontend/src/routes/forgot-password.tsx`, `frontend/src/routes/reset-password.tsx`
- **REQs**: REQ-SOS-04, REQ-SOS-05 / D-05, D-10
- **Depends on**: Phase 5 must land in same commit
- **Description**: Delete all four route files. TanStack Router file-based routing removes the routes automatically on next dev/build.

### T-4-04: Delete authenticated subscription and usage route directories
- **Files**: `frontend/src/routes/_authenticated/subscription/index.tsx`, `frontend/src/routes/_authenticated/usage/index.tsx`
- **REQs**: REQ-SOS-06 / D-05
- **Depends on**: Phase 5 must land in same commit
- **Description**: Delete both route files (and their containing dirs if they become empty).

### T-4-05: Delete VerificationBanner component
- **Files**: `frontend/src/features/users/components/VerificationBanner.tsx`
- **REQs**: REQ-SOS-09 / D-05
- **Depends on**: Phase 5 must land in same commit
- **Description**: Delete the `VerificationBanner.tsx` file. Remove its export from `frontend/src/features/users/index.ts`.

---

## Phase 5 — Frontend consumer edits (atomic with Phase 4)

### T-5-01: Edit login.tsx — remove signup and forgot-password links
- **Files**: `frontend/src/routes/login.tsx`
- **REQs**: REQ-SOS-07 / D-06
- **Depends on**: T-4-03 (route files gone)
- **Description**: Remove the `<p>` block containing "¿No tiene cuenta? Regístrese" (lines 87-92). Remove the "¿Olvidaste tu contraseña?" link block (lines ~64-70). Login form must contain only credential fields and submit button.

### T-5-02: Edit _authenticated.tsx — remove SaaS nav, VerificationBanner, QuotaExceededDialog
- **Files**: `frontend/src/routes/_authenticated.tsx`
- **REQs**: REQ-SOS-08, REQ-SOS-09, REQ-SOS-10 / D-07
- **Depends on**: T-4-01 (subscription dir gone), T-4-02 (usage dir gone), T-4-05 (banner gone)
- **Description**: Remove `VerificationBanner` import and its render at line 32. Remove `QuotaExceededDialog` import and render at line 91. Remove `<Link to="/usage">` block (lines 52-58) and `<Link to="/subscription">` block (lines 59-65) and their role-based gating.

### T-5-03: Edit api-client.ts — remove QUOTA_EXCEEDED_EVENT dispatch
- **Files**: `frontend/src/shared/lib/api-client.ts`
- **REQs**: REQ-SOS-10 / D-07
- **Depends on**: T-4-01 (subscription dir gone)
- **Description**: Remove `QUOTA_EXCEEDED_EVENT` import (line 2) and the 429/quota dispatch block (lines 36-40). 429 responses must still propagate normally — only the custom event dispatch is removed.

### T-5-04: Edit auth.tsx — remove email_verified field and signup method
- **Files**: `frontend/src/shared/lib/auth.tsx`
- **REQs**: REQ-SOS-04 (dead code), D-05
- **Depends on**: T-4-03 (signup route gone)
- **Description**: Remove `email_verified: boolean` from the `User` interface (line 9). Remove `signup` method from `AuthContextType` (line 16), its implementation (lines 45-64), and from the context value (line 74).

### T-5-05: Edit users/index.tsx — count-only badge, remove useTenantTier
- **Files**: `frontend/src/routes/_authenticated/users/index.tsx`
- **REQs**: REQ-SOS-16 / D-09
- **Depends on**: T-4-01 (subscription/api/queries gone)
- **Description**: Remove `useTenantTier` import (line 4). Replace the `tierData`/`userUsage` logic with the user count from the existing `useUsers()` query length. Change badge to display `{count} usuarios` with no slash/denominator. Remove all `userUsage`, `tierData`, `near_limit` references.

---

## Phase 6 — Test cleanup

### T-6-01: Delete stale integration test files
- **Files**: `backend/tests/integration/test_signup_api.py`, `test_tiers_api.py`, `test_usage_api.py`
- **REQs**: D-12
- **Depends on**: T-1-01, T-1-03
- **Description**: Delete all three files. They test endpoints that are now 404. Per D-12, we do NOT write 404 assertions for unrouted endpoints.

### T-6-02: Delete or update password reset integration tests
- **Files**: `backend/tests/integration/test_users_password_reset.py` (and any forgot-password test file)
- **REQs**: REQ-SOS-02 / D-12
- **Depends on**: T-1-02
- **Description**: Review `test_users_password_reset.py` — if it tests the now-removed self-service `/auth/forgot-password` and `/auth/reset-password` handlers, delete or trim the relevant tests. Admin-driven password reset (via `/users/{id}/password`) is a different flow — keep those tests.

### T-6-03: Update test_users_api.py — remove quota mock from create_user
- **Files**: `backend/tests/integration/test_users_api.py`
- **REQs**: REQ-QSI-10 / D-04
- **Depends on**: T-3-03
- **Description**: Remove any `fake_quota_service` setup or `check_user_limit` mock assertions from the `create_user` test. The quota call is gone from the handler; the test should not rely on it.

---

## Phase 7 — Verification gate

### T-7-01: Run full backend test suite
- **Files**: —
- **REQs**: All
- **Depends on**: Phases 1-6 complete
- **Description**: Run `docker compose exec -T api pytest -q` from the project root. Expected: ~530-540 passing (down from 565 due to deleted stale files + new tests from Phases 2-3). 0 failing, 0 regressions.

### T-7-02: Run frontend TypeScript type-check
- **Files**: —
- **REQs**: REQ-SOS-17
- **Depends on**: Phases 4-5 complete (atomic commit)
- **Description**: Run `npx tsc --noEmit -p tsconfig.app.json` from `frontend/`. Must exit 0.

### T-7-03: Run frontend ESLint
- **Files**: —
- **REQs**: REQ-SOS-18
- **Depends on**: Phases 4-5 complete
- **Description**: Run `npm run lint` from `frontend/`. Must report 0 errors. 4 pre-existing warnings in shadcn primitives and `auth.tsx` are tolerated.

---

## Estimate

| Phase | Tasks | Focus | Est. |
|-------|-------|-------|------|
| 1 | 4 | Backend route disabling | ~25 min |
| 2 | 2 | QuotaService silencing (TDD) | ~30 min |
| 3 | 6 | documents.py, users.py, auth/me, entity | ~35 min |
| 4 | 5 | Frontend deletions | ~10 min |
| 5 | 5 | Frontend consumer edits | ~40 min |
| 6 | 3 | Test cleanup | ~20 min |
| 7 | 3 | Verification gate | ~15 min |
| **Total** | **28** | | **~3 hrs** |

## Commit strategy

- **Commit A**: Phases 1-3 (backend changes + backend test updates)
- **Commit B**: Phases 4+5 together (atomic frontend deletion + consumer fixes — must stay clean for `tsc --noEmit`)
- **Commit C**: Phase 6 (test cleanup — separate for clarity)
- **Commit D**: Phase 7 verification artifacts (if any scripts/notes needed)
