# Archive Report: single-org-cutover

**Change ID**: single-org-cutover  
**Archived**: 2026-04-27  
**Status**: CLOSED — Ready for deployment

---

## Change Summary

**Intent**: Convert SigDoc's user-facing surface from multi-tenant SaaS to a single-organization system for CAINCO acquisition, keeping the multi-tenant schema intact under the hood. Nivel A locked approach.

**Scope**: Remove signup, email-verification, subscription/usage pages, self-service password reset, and quota enforcement from the UI and API surface. Preserve multi-tenant DB schema for reversibility.

---

## Implementation Completion

### Specifications Implemented

Two new capabilities defined and fully implemented:

| Capability | REQs | SCENs | Status |
|------------|------|-------|--------|
| `single-org-surface` | 20 | 14 | ✅ Implemented + Verified |
| `quota-silencing` | 11 | 6 | ✅ Implemented + Verified |
| **TOTAL** | **31** | **20** | ✅ ALL IMPLEMENTED |

### Task Completion

All **28/28 tasks** completed across 7 phases:

| Phase | Focus | Tasks | Status | Commit |
|-------|-------|-------|--------|--------|
| 1 | Backend route disabling | 4/4 | ✅ Complete | 7472cf8 |
| 2 | QuotaService silencing | 2/2 | ✅ Complete | feb2459 |
| 3 | Email verification removal | 6/6 | ✅ Complete | 6580dad |
| 4+5 | Frontend atomic cutover | 9/9 | ✅ Complete | 7414bf4 |
| 6+7 | Test cleanup + verification | 7/7 | ✅ Complete | 420ebb1 |

---

## Final Test Results

### Backend Test Suite
- **Status**: ✅ **553 passed, 0 failed**
- **Warnings**: 32 pre-existing SQLAlchemy async RuntimeWarnings (not caused by this change)
- **Coverage**: All 31 requirements verified by 20 scenario tests + unit + integration tests

### Frontend Quality Gates
- **TypeScript**: ✅ `npx tsc --noEmit -p tsconfig.app.json` → EXIT 0
- **ESLint**: ✅ `npm run lint` → 0 errors, 4 pre-existing warnings (tolerated in shadcn primitives + auth.tsx)
- **Smoke Test**: ✅ Login page contains 0 signup/forgot-password references

### Test Deletions (Phase 6)
Stale test files deleted:
- `backend/tests/integration/test_signup_api.py` (236 lines)
- `backend/tests/integration/test_tiers_api.py` (464 lines)
- `backend/tests/integration/test_usage_api.py` (216 lines)

Trimmed:
- `backend/tests/integration/test_auth_api.py` — removed 7 self-service auth tests; kept admin password reset tests

---

## Canonical Specifications

Two new specs synced to `openspec/specs/`:

| Spec | Purpose | Artifacts |
|------|---------|-----------|
| `openspec/specs/single-org-surface.md` | User-facing surface contract (routes, links, invariants) | 20 REQs, 14 SCENs |
| `openspec/specs/quota-silencing.md` | Quota enforcement no-op semantics with reversibility | 11 REQs, 6 SCENs |

**Path**: `/home/devrafaseros/projects/GITHUB/PERSONAL/sigdoc/openspec/specs/`

Canonical specs are now the source of truth. Changes are archived.

---

## Commits in This Change

| Hash | Subject | Phase |
|------|---------|-------|
| `7472cf8` | feat(cutover): disable SaaS endpoints | Phase 1 |
| `feb2459` | feat(cutover): silence QuotaService | Phase 2 |
| `6580dad` | feat(cutover): remove email-verification gate | Phase 3 |
| `7414bf4` | feat(cutover): remove SaaS UI atomically | Phases 4+5 |
| `420ebb1` | test(cutover): clean stale tests | Phases 6+7 |

---

## Archive Contents

Change folder: `openspec/changes/archive/2026-04-27-single-org-cutover/`

Preserved artifacts:
- ✅ `proposal.md` — original intent + scope
- ✅ `explore.md` — research phase findings
- ✅ `spec/single-org-surface.md` — surface contract
- ✅ `spec/quota-silencing.md` — quota semantics
- ✅ `design.md` — technical design decisions (D-01 through D-13)
- ✅ `tasks.md` — task breakdown + conventions
- ✅ `apply-progress.md` — implementation log + commit hashes
- ✅ `archive-report.md` — this file

All artifacts preserved for audit trail and future Nivel B reference.

---

## Deferred Work (Nivel B and C)

### Nivel B (RECOMMENDED for next phase)
1. Drop `subscription_tiers`, `usage_events`, `rate_limits` tables
2. Remove `QuotaService` class entirely (currently silenced via `_QUOTA_DISABLED=True`)
3. Remove unrouted handler files:
   - `backend/src/app/application/services/signup_service.py`
   - `backend/src/app/application/services/email_verification_service.py`
   - `backend/src/app/application/services/password_reset_service.py`
4. Remove unrouted handler files from presentation layer:
   - `backend/src/app/presentation/api/v1/tiers.py`
   - `backend/src/app/presentation/api/v1/usage.py`
5. Migration 013: Drop `email_verified`, `email_verification_token`, `email_verification_sent_at` columns from `users` table
6. Refactor `TierPreloadMiddleware` to stub tier with no limits (since tiers table will be gone)

### Nivel C (NOT RECOMMENDED)
1. Drop `tenants` table entirely
2. Remove `tenant_id` from all tables
3. Refactor `TenantMiddleware` to hard-wire singleton tenant context

---

## Key Reversibility Properties

✅ **Multi-tenant DB schema is intact** — All tables, columns, and foreign keys unchanged.

✅ **QuotaService is reversible** — Setting `_QUOTA_DISABLED = False` restores full quota enforcement. Unit tests verify this (SCEN-QSI-11).

✅ **Deprecated services marked** — `signup_service.py`, `email_verification_service.py`, `password_reset_service.py` carry module docstring `"""DEPRECATED: route disabled per single-org-cutover; remove in Nivel B."""`

✅ **Route removal is clean** — Handlers deleted from auth.py; include_router removed from main.py. Re-enabling is a straightforward add-back.

✅ **Email verification always true** — Hardcoded in both response layer and domain entity. Database column may still hold `false`; field is ignored.

---

## Sign-Off

- ✅ All 28 tasks complete
- ✅ All 31 requirements implemented
- ✅ All 20 scenarios verified
- ✅ Backend: 553 tests passing
- ✅ Frontend: TypeScript clean, ESLint clean
- ✅ No regressions introduced
- ✅ Change ready for deployment

**Approved for merge and deployment.**

---

## Related Observations

**Engram observations** (for cross-session traceability):
- [#285] Exploration: single-org-cutover
- [#286] Proposal: single-org-cutover
- [#287] Specs: single-org-surface + quota-silencing
- [#288] Tasks: single-org-cutover
- [#289] Apply Progress: single-org-cutover (FINAL)

See openspec/changes/archive/2026-04-27-single-org-cutover/ for full artifact trail.
