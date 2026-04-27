# Proposal: single-org-cutover

## Intent

CAINCO has acquired SigDoc as an internal tool. The SaaS-facing surface (self-service signup, email verification, tier/usage pages, self-service password reset, quota enforcement) is no longer needed — the user is sole operator and admin. We strip the user-visible SaaS pieces (Nivel A — cosmetic + silencing) while preserving the multi-tenant DB schema, services, and middleware so a future direction shift remains reversible. No schema changes, no architectural refactor.

## Scope

### In Scope
- Remove frontend SaaS routes: `/signup`, `/verify-email`, `/subscription`, `/usage`, `/forgot-password`, `/reset-password`
- Remove frontend SaaS components: `features/subscription/`, `features/usage/`, `VerificationBanner`, `QuotaExceededDialog` event wiring
- Remove login-page links: "Regístrese" and "¿Olvidaste tu contraseña?"
- Remove auth nav links to `/usage` and `/subscription` (and their role-gating)
- Disable backend routers/handlers: `/auth/signup`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password`, `/api/v1/tiers/*`, `/api/v1/usage/*`
- Remove `_require_verified_email` dep from `documents.py` (both call sites)
- Hardcode `email_verified=True` in `/auth/me` response and domain entity default
- Silence `QuotaService.check_*` and `get_usage_summary` via `_QUOTA_DISABLED = True` flag (keep `get_tier_for_tenant` LIVE for `TierPreloadMiddleware` rate limits)
- Delete stale integration test files (`test_signup_api.py`, `test_tiers_api.py`, `test_usage_api.py`, password-reset integration tests)
- Update `_authenticated/users/index.tsx` admin user count: drop `/ ${limit}` denominator (count-only display)
- Mark deprecated handler files with single-line docstring (`signup_service.py`, `email_verification_service.py`, password reset)

### Out of Scope (deferred to Nivel B / Nivel C)
- DROP `subscription_tiers`, `usage_events`, `rate_limits` tables (Nivel B)
- DROP `tenants` table or `tenant_id` columns (Nivel C)
- Refactor or remove `TenantMiddleware` (Nivel C)
- Remove the `QuotaService` class entirely (Nivel B)
- Delete deprecated `signup_service.py`, `email_verification_service.py`, `password_reset_service.py` files (Nivel B)
- Drop `email_verified`, `email_verification_token`, `email_verification_sent_at`, `password_reset_*` columns (Nivel B migration `013`)
- Backfill existing `email_verified=False` rows to `True` (not needed; field is no longer read)
- Schema migration of any kind — head stays at `012_demo_reset`

## Capabilities

### New Capabilities
- `single-org-surface`: Defines the post-cutover user-facing surface — which routes/endpoints exist, which return 404, which links are present in the login page and authenticated nav. Locks the cosmetic contract for Nivel A.
- `quota-silencing`: Defines the `_QUOTA_DISABLED` flag semantics, which `QuotaService` methods short-circuit, which stay live (`get_tier_for_tenant`), and the invariant that document/template/user creation never 429s on quota.

### Modified Capabilities
- None. The 4 existing specs (`document-download-format`, `pdf-conversion`, `role-model`, `template-management-permissions`) are unaffected — their requirements don't touch the SaaS surface.

## Approach

Atomic single-batch removal: delete frontend feature dirs and routes in one commit so TypeScript stays valid throughout. Backend disables routes via handler removal (signup, verify-email, resend-verification, forgot-password, reset-password) and `include_router` removal in `main.py` (usage, tiers). `QuotaService` gets a class-level `_QUOTA_DISABLED = True` constant and each guarded method early-returns a no-op stub. Deprecated service files keep a one-line docstring marker for Nivel B grep.

### Locked Decisions

- **D-01 — Disable strategy**: `/auth/signup`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/forgot-password`, `/auth/reset-password` → remove handlers from `auth.py` (handlers are local). `/usage`, `/tiers` → remove `include_router` lines from `main.py` (router-level). Service files (`signup_service`, `email_verification_service`, `password_reset_service`) stay for Nivel B reversibility.
- **D-02 — `_require_verified_email`**: Remove function (`documents.py:47-68`) and both `Depends(...)` call sites (lines 85, 170). No other endpoint uses it.
- **D-03 — `email_verified` schema preservation**: Column stays. Hardcode `email_verified=True` in `/auth/me` (`auth.py:209`) and domain entity default (`user.py:19`). Belt-and-suspenders since frontend stops reading the field.
- **D-04 — `QuotaService` silencing pattern**: Class-level `_QUOTA_DISABLED = True` constant. `check_document_quota`, `check_template_limit`, `check_user_limit`, `check_bulk_limit`, `check_share_limit`, `get_usage_summary` early-return stubs when flag is `True`. `get_tier_for_tenant` stays unguarded — `TierPreloadMiddleware` needs it for slowapi rate-limit tier resolution. Rate limiting is API protection, not SaaS — it stays.
- **D-05 — Frontend deletion strategy**: Delete entire feature dirs (`features/subscription/` 6 files, `features/usage/` 6 files), entire route dirs (`_authenticated/subscription/`, `_authenticated/usage/`), individual route files (`signup.tsx`, `verify-email.tsx`, `forgot-password.tsx`, `reset-password.tsx`), and `VerificationBanner.tsx`. All in one commit so `tsc --noEmit` stays clean.
- **D-06 — Login page edits**: Remove `<p>` block "¿No tiene cuenta? Regístrese" (`login.tsx:87-92`) AND remove "¿Olvidaste tu contraseña?" link (`login.tsx:64` area).
- **D-07 — Auth navigation**: Remove `<Link to="/usage">` (`_authenticated.tsx:52-58`), `<Link to="/subscription">` (`_authenticated.tsx:59-65`), and their role-based gating. Also remove `VerificationBanner` render (line 32) and `QuotaExceededDialog` render (line 91).
- **D-08 — Email-sending audit on user creation**: Lock contract: `POST /users` (admin-create-user) emits zero email side effects. Spec phase produces a unit/integration test asserting no `EmailVerificationService` or `PasswordResetService` interaction during admin user creation.
- **D-09 — Admin user list count**: Verified current state still renders `{userUsage.limit !== null ? \` / ${userUsage.limit}\` : ""} usuarios` (`_authenticated/users/index.tsx:36-37`). Change to count-only: `{userUsage.used} usuarios`. Drop the conditional and the entire `userUsage.limit` reference. (Keep `userUsage.used` source if the tier API still returns it — once `/tiers/tenant` is unrouted this whole `userUsage` block needs to read from a different source or be dropped; the spec phase resolves the data source.)
- **D-10 — TanStack file-based routes**: Removing `routes/*.tsx` files removes routes automatically; `routeTree.gen.ts` regenerates on next dev/build. No manual route registration to clean.
- **D-11 — Backend handler files kept**: `signup_service.py`, `email_verification_service.py`, `password_reset_service.py`, plus `auth.py` handler bodies for the password reset endpoints, are deleted from routing surface but the service files persist. Add single-line module docstring `"""DEPRECATED: route disabled per single-org-cutover; remove in Nivel B."""` to each.
- **D-12 — Tests strategy**: Delete `test_signup_api.py` (236 lines), `test_tiers_api.py` (464 lines), `test_usage_api.py` (216 lines), and any `test_password_reset_api.py` / forgot-password integration tests in this batch. We don't write 404 assertions for unrouted endpoints — that's testing FastAPI/TanStack router itself. Spec phase generates a small set of cutover-invariant smoke tests instead.
- **D-13 — Spec module count**: Two specs (`single-org-surface` + `quota-silencing`). Splitting them keeps the surface contract (URL/route invariants, login/nav link list) separate from the runtime behavior contract (no 429s, `_QUOTA_DISABLED` semantics, `get_tier_for_tenant` exemption). Two narrow specs are cheaper to verify than one wide one.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/src/routes/signup.tsx` | Removed | Self-service signup route |
| `frontend/src/routes/verify-email.tsx` | Removed | Email verification landing |
| `frontend/src/routes/forgot-password.tsx` | Removed | Self-service password reset entry |
| `frontend/src/routes/reset-password.tsx` | Removed | Token-based password reset form |
| `frontend/src/routes/_authenticated/subscription/` | Removed | Tier + usage page (entire dir) |
| `frontend/src/routes/_authenticated/usage/` | Removed | Usage stats page (entire dir) |
| `frontend/src/features/subscription/` | Removed | 6 files: `QuotaExceededDialog`, `TierCard`, `api/*` |
| `frontend/src/features/usage/` | Removed | 6 files: `UsageWidget`, `TenantUsageTable`, `api/*` |
| `frontend/src/features/users/components/VerificationBanner.tsx` | Removed | Email verification banner |
| `frontend/src/routes/login.tsx` | Modified | Drop "Regístrese" block + "¿Olvidaste tu contraseña?" link |
| `frontend/src/routes/_authenticated.tsx` | Modified | Drop `VerificationBanner`, `QuotaExceededDialog`, `/usage` nav, `/subscription` nav |
| `frontend/src/routes/_authenticated/users/index.tsx` | Modified | Drop `/ ${limit}` denominator from user count |
| `frontend/src/shared/lib/api-client.ts` | Modified | Drop `QUOTA_EXCEEDED_EVENT` import + 429-quota dispatch (lines 2, 36-40) |
| `frontend/src/shared/lib/auth.tsx` | Modified | Drop `email_verified` field, `signup` method + impl |
| `frontend/src/features/users/index.ts` | Modified | Drop `VerificationBanner` export |
| `backend/src/app/main.py` | Modified | Drop `usage` + `tiers` router includes (lines 71, 73), clean import |
| `backend/src/app/presentation/api/v1/auth.py` | Modified | Drop `signup` (42-91), `verify_email` (256-277), `resend_verification` (280-317), `/forgot-password`, `/reset-password` handlers; hardcode `email_verified=True` (line 209); clean unused imports |
| `backend/src/app/presentation/api/v1/documents.py` | Modified | Drop `_require_verified_email` (47-68) and both call sites (85, 170) |
| `backend/src/app/presentation/api/v1/users.py` | Modified | Drop `quota_service.check_user_limit` call from `create_user` |
| `backend/src/app/presentation/schemas/auth.py` | Modified | Drop `SignupRequest`, `SignupResponse`, `SignupUserResponse` |
| `backend/src/app/application/services/quota_service.py` | Modified | Add `_QUOTA_DISABLED = True`; early-return in 5 `check_*` + `get_usage_summary` |
| `backend/src/app/domain/entities/user.py` | Modified | Default `email_verified: bool = True` (was `False`) |
| `backend/src/app/application/services/signup_service.py` | Modified (docstring only) | Single-line "DEPRECATED" marker |
| `backend/src/app/application/services/email_verification_service.py` | Modified (docstring only) | Single-line "DEPRECATED" marker |
| `backend/src/app/application/services/password_reset_service.py` | Modified (docstring only) | Single-line "DEPRECATED" marker |
| `backend/src/app/presentation/api/v1/usage.py` | No change | Router not included; file kept for Nivel B |
| `backend/src/app/presentation/api/v1/tiers.py` | No change | Router not included; file kept for Nivel B |
| `backend/src/app/presentation/middleware/rate_limit.py` | No change | `TierPreloadMiddleware` stays active |
| `backend/alembic/versions/` | No change | Head stays at `012_demo_reset` |
| `tests/integration/test_signup_api.py` | Removed | 236 lines, entirely stale |
| `tests/integration/test_tiers_api.py` | Removed | 464 lines, router disabled |
| `tests/integration/test_usage_api.py` | Removed | 216 lines, router disabled |
| `tests/integration/test_password_reset_api.py` (or equivalent) | Removed | Endpoints removed |
| `tests/integration/test_auth_api.py` | Modified | Drop `email_verified` assertions, signup-related stubs |
| `tests/integration/test_documents_api.py` | Modified | Drop T-VERIFY-15 block (`_require_verified_email` tests) |
| `tests/integration/test_users_api.py` | Modified | Drop quota mock from `create_user` test |
| `tests/unit/test_quota_service.py` | Modified | Override `_QUOTA_DISABLED=False` for legacy tests; add tests for the silenced default |
| `tests/unit/test_signup_service.py` | No change | Service still exists |
| `tests/unit/test_email_verification_service.py` | No change | Service still exists |
| `tests/unit/test_usage_service.py` | No change | Service still exists |

## Migration Plan

**No schema migration in this batch.** Alembic head stays at `012_demo_reset`. The `email_verified`, `email_verification_token`, `email_verification_sent_at`, `password_reset_token`, `password_reset_sent_at` columns remain in the `users` table. Their values are no longer read by the application. Nivel B will introduce migration `013` to drop these columns and the `subscription_tiers` / `usage_events` / `rate_limits` tables.

Demo VPS (`sigdoc.devrafaseros.com`) is already on `012` post-deploy; no DB action needed for cutover.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| TypeScript compile errors from broken imports during partial deletion | Med | Atomic single-commit deletion of all `features/subscription/`, `features/usage/`, the routes, AND the `_authenticated.tsx` / `api-client.ts` / `auth.tsx` modifications together. CI `tsc --noEmit` gates the PR. |
| `TierPreloadMiddleware` accidentally broken if `get_tier_for_tenant` is silenced | Low | Spec phase pins explicit invariant: `get_tier_for_tenant` is exempt from `_QUOTA_DISABLED`; verify-phase test asserts an authenticated request still gets `request.state.tier` populated. |
| Existing `email_verified=False` rows leak through `/auth/me` | Low | D-03: hardcode `email_verified=True` in response builder unconditionally. Field is no longer rendered anyway. |
| Stale integration tests for removed endpoints leave the suite red | Low | D-12: delete the stale files in this batch, do not leave 404-asserting tests behind. |
| Test count regression alarms ("we lost 30 tests!") | Low | Document new baseline (~530-540) in success criteria. Verify-phase report makes the delta explicit. |
| Forgot-password is reintroduced later if CAINCO changes mind | Low | Service files (`password_reset_service.py`) preserved; D-11 docstring marker makes Nivel B grep trivial. Re-enabling = re-add handler + frontend route. |
| Admin user count display breaks because `/tiers/tenant` is unrouted | Med | D-09 spec phase resolves data source: either count from existing user-list query (length), or call a different endpoint. The `/tiers/tenant` API call must be replaced or removed in this batch. |
| Rate-limit middleware breaks if `subscription_tiers` table is empty | Low | Migration `012_demo_reset` already seeds one tier row for the singleton tenant. Verified in `test_demo_reset_migration.py`. |

## Rollback Plan

1. **Revert the cutover commit(s)** via `git revert` — single atomic commit makes this clean.
2. Frontend redeploys with all SaaS routes restored (TanStack route tree regenerates on build).
3. Backend redeploys with handlers and `include_router` calls restored; `_QUOTA_DISABLED` returns to `False` (or constant removed entirely).
4. DB schema is unchanged — no down-migration needed.
5. Existing user `email_verified` values are intact; if some users had `False`, they would need to verify post-rollback (or admin can backfill via a one-line SQL UPDATE).
6. Tests reintroduced via revert; baseline returns to 565.

Estimated rollback time: < 10 minutes (one revert + GH Actions deploy).

## Dependencies

- Migration `012_demo_reset` already deployed on demo VPS (singleton tenant + admin seeded).
- GH Actions deploy pipeline functioning (sigdoc.devrafaseros.com).
- `_QUOTA_DISABLED` flag pattern is greenfield (no existing prior art in this codebase to align with).

## Success Criteria

- [ ] Browser routes return 404: `/signup`, `/verify-email`, `/forgot-password`, `/reset-password`, `/subscription`, `/usage`
- [ ] API endpoints return 404: `/api/v1/auth/signup`, `/api/v1/auth/verify-email`, `/api/v1/auth/resend-verification`, `/api/v1/auth/forgot-password`, `/api/v1/auth/reset-password`, `/api/v1/tiers/*`, `/api/v1/usage/*`
- [ ] Login page contains no "Regístrese" link and no "¿Olvidaste tu contraseña?" link
- [ ] Authenticated nav contains no "Suscripción" or "Uso" links
- [ ] Admin can log in, manage users, generate single + bulk documents, manage templates (regression-safe)
- [ ] Bulk document generation at any quantity does NOT return HTTP 429 due to quota (rate-limit 429 still possible per slowapi — distinct)
- [ ] `/auth/me` returns `email_verified: true` for every authenticated user, regardless of DB row value
- [ ] Frontend `pnpm tsc --noEmit` exits 0
- [ ] Frontend `pnpm lint` shows 0 errors (4 pre-existing warnings preserved)
- [ ] Backend `pytest` passes; expected count ~530-540 (down from 565 due to deleted stale test files)
- [ ] Alembic head: `alembic current` reports `012_demo_reset`
- [ ] `TierPreloadMiddleware` populates `request.state.tier` on authenticated requests (verified by an integration test)
- [ ] Demo VPS deploy: GH Actions green, smoke test 200, login still works, document generation works
