# Apply Progress — single-org-cutover

## Batch 1 — Phase 1: Backend route disabling (2026-04-27)

### Tasks Completed

- [x] **T-1-01** — Removed `signup`, `verify_email`, `resend_verification` handlers from `auth.py`. Cleaned imports: `EmailVerificationService`, `SignupService`, `SignupError`, `SignupRequest`, `SignupResponse`, `SignupUserResponse`, `SQLAlchemyTenantRepository`, `SQLAlchemySubscriptionTierRepository`, `get_email_service`, `Query`.
- [x] **T-1-02** — Removed `forgot_password`, `reset_password` handler functions from `auth.py`. Cleaned imports: `PasswordResetService`, `ForgotPasswordRequest`, `ResetPasswordRequest`.
- [x] **T-1-03** — Removed `usage.router` and `tiers.router` includes from `main.py`. Removed `usage, tiers` from the module import on line 12.
- [x] **T-1-04** — Added `DEPRECATED: route disabled per single-org-cutover; remove in Nivel B.` module-level docstring to `signup_service.py`, `email_verification_service.py`, `password_reset_service.py`.

### Files Modified

| File | Action | What Was Done |
|------|--------|---------------|
| `backend/src/app/presentation/api/v1/auth.py` | Modified | Removed signup/verify/resend/forgot/reset handlers + unused imports |
| `backend/src/app/main.py` | Modified | Removed `usage` and `tiers` router includes + imports |
| `backend/src/app/application/services/signup_service.py` | Modified | Added DEPRECATED module docstring |
| `backend/src/app/application/services/email_verification_service.py` | Modified | Added DEPRECATED module docstring |
| `backend/src/app/application/services/password_reset_service.py` | Modified | Added DEPRECATED module docstring |

### Tests Added

| File | Action | Coverage |
|------|--------|----------|
| `backend/tests/integration/test_unrouted_endpoints.py` | Created | 7 parametrized 404 assertions for all removed endpoints |

**Smoke test results**: 7/7 PASSED
- POST /api/v1/auth/signup → 404 ✓
- GET  /api/v1/auth/verify-email → 404 ✓
- POST /api/v1/auth/resend-verification → 404 ✓
- POST /api/v1/auth/forgot-password → 404 ✓
- POST /api/v1/auth/reset-password → 404 ✓
- GET  /api/v1/tiers → 404 ✓
- GET  /api/v1/usage → 404 ✓

### Final Test Count

| Category | Count |
|----------|-------|
| Passed   | 542   |
| Failed   | 42    |
| Total    | 584   |

**Failure breakdown by file:**

| File | Failures | Cause | Phase to fix |
|------|----------|-------|--------------|
| `test_signup_api.py` | 7 | Signup route now 404 | Phase 6 (T-6-01: delete file) |
| `test_tiers_api.py` | 11 | Tiers router unrouted | Phase 6 (T-6-01: delete file) |
| `test_usage_api.py` | 7 | Usage router unrouted | Phase 6 (T-6-01: delete file) |
| `test_auth_api.py` | 7 | verify-email/forgot/reset handlers gone | Phase 6 (T-6-02: trim tests) |
| `test_quota_service.py` | 7 | **Pre-existing** — `monthly_document_limit`/`unlimited_usage` not on User entity | Phase 2 (T-2-02) will add flag, may need entity update |
| `test_users_api.py` | 3 | **Pre-existing** — `unlimited_usage` field missing from User entity | Phase 2 or Phase 6 (T-6-03) |

### Pre-Existing Failures (not caused by Phase 1)

Baseline before Phase 1: **10 pre-existing failures** in `test_quota_service.py` (7) and `test_users_api.py` (3). These fail because they reference `monthly_document_limit` and `unlimited_usage` fields not yet on the `User` entity. They will be addressed in Phase 2 (quota service implementation).

### Deviations from Design

None. Implementation matches design decisions D-01 and D-11 exactly.

### Risks for Phase 2

- `test_quota_service.py` failures suggest the `User` entity needs `monthly_document_limit` and `unlimited_usage` fields — Phase 2 should add these to the entity if they don't exist yet, or the pre-existing test failures will remain.
- The `_quota_exceeded_handler` and `QuotaExceededError` exception handler remain in `main.py` — Phase 2 will leave them (they're needed as long as quota enforcement can still be toggled via `_QUOTA_DISABLED=False`).

## Next Batch

Phase 2 — T-2-01, T-2-02: QuotaService `_QUOTA_DISABLED` flag (TDD).
