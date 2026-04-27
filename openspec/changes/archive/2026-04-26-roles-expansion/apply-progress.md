# Apply Progress — roles-expansion

**Mode**: Strict TDD
**Artifact store**: hybrid (engram + openspec)

---

## Phase 1 — Domain & Permissions (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-DOMAIN-01 | ✅ DONE | Extended truth tables in `test_permissions.py` with `template_creator` + `document_generator` rows |
| T-DOMAIN-02 | ✅ DONE | Audited existing helpers — all use `role == "admin"`, already correct; no impl change needed |
| T-DOMAIN-03 | ✅ DONE | Added `can_manage_own_templates` truth table (4 rows) to `test_permissions.py` |
| T-DOMAIN-04 | ✅ DONE | Implemented `can_manage_own_templates` in `permissions.py`, added to `__all__` |
| T-DOMAIN-05 | ✅ DONE | Created `test_user_entity.py` with 4 tests for entity default role |
| T-DOMAIN-06 | ✅ DONE | Changed `User.role` default from `"user"` to `"document_generator"` |

### TDD Evidence

| Task | Group | RED | GREEN |
|------|-------|-----|-------|
| T-DOMAIN-01 | B | n/a (new rows PASS immediately — existing helpers already return False for non-admin) | 14 new rows, all PASS |
| T-DOMAIN-02 | B | — | Audited, no change needed |
| T-DOMAIN-03 | A | 4 FAIL (ImportError: `can_manage_own_templates` not found) | 4 PASS after implementation |
| T-DOMAIN-04 | A | — | Helper added, RED→GREEN cycle via T-DOMAIN-03 |
| T-DOMAIN-05 | C | 2 FAIL (`role='user' != 'document_generator'`) | 4 PASS after entity default change |
| T-DOMAIN-06 | C | — | Entity default changed, all GREEN |

### Files Changed

| File | Action | What |
|------|--------|------|
| `backend/src/app/domain/services/permissions.py` | Modified | Added `can_manage_own_templates(role) -> bool`; added to `__all__` |
| `backend/src/app/domain/entities/user.py` | Modified | `role: str = "user"` → `role: str = "document_generator"` (line 13) |
| `backend/tests/unit/domain/test_permissions.py` | Modified | Extended ROLE_EXPECTATIONS (5 rows: admin/user/template_creator/document_generator/unknown); added `can_manage_own_templates` parametrized table (4 rows) |
| `backend/tests/unit/domain/test_user_entity.py` | Created | New file — 4 tests for User entity default role (REQ-ROLE-04, SCEN-ROLE-09) |
| `openspec/changes/roles-expansion/tasks.md` | Modified | Marked T-DOMAIN-01..06 with ✅ |

### Tests Added

- **`test_permissions.py`**: +18 new parametrized rows (7 helpers × 2 new roles) + 4 `can_manage_own_templates` rows = **22 new test cases** (counting parametrized instances)
  - Actually: `test_permissions.py` had 22 collected before, now has 40 → **+18 from existing helpers + 4 new = +22 new test functions** (parametrized instances)
- **`test_user_entity.py`**: **4 new test methods**

Total new tests: **22** (verified: 495 - 473 = 22)

### Tests Modified

- **None** — the entity default change caused zero regressions. All existing tests that construct `User()` use explicit `role=` kwargs. No test relied on the old `"user"` default implicitly.

### Final Test Count

**495 passing, 0 failing** (baseline was 473)

---

## Infrastructure Note

- `backend/src/` IS volume-mounted in the container → source changes are immediate
- `backend/tests/` is NOT volume-mounted → modified/new test files must be `docker cp`'d to `docker-api-1:/code/tests/`

---

## Risks / Blockers for Phase 2

1. **`test_middleware.py` line 83** asserts `result.role == "user"` for the middleware fallback when no `role` claim is in the token. T-INFRA-06 changes `presentation/middleware/tenant.py:44` fallback from `"user"` to `"document_generator"`. **Phase 2 agent MUST update this test** when implementing T-INFRA-06 (and `docker cp` the updated file).

2. **Tests not volume-mounted**: Every new or modified test file must be copied into the running container before running pytest.

3. **Migration ordering**: T-INFRA-03 `upgrade()` must run `UPDATE` before `ALTER DEFAULT` — verified in design.md ADR-ROLE-02.

---

## Phase 2 — Infrastructure (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-INFRA-01 | ✅ DONE | Verified: `010_pdf_export.py` is latest, `011` slot free. `down_revision="010"` confirmed. |
| T-INFRA-02 | ✅ DONE | Created `test_role_migration.py` (9 tests): metadata, upgrade order, downgrade order — mocks `alembic.op` to verify SQL statement sequence |
| T-INFRA-03 | ✅ DONE | Created `011_role_expansion.py`; upgrade/downgrade in correct ADR-ROLE-02 order; lossy downgrade documented in docstring |
| T-INFRA-04 | ✅ DONE | Created `test_user_model_defaults.py` (2 tests): asserts `col.default.arg == "document_generator"` and `col.server_default.arg == "document_generator"` |
| T-INFRA-05 | ✅ DONE | Changed `UserModel.role` column: `default="document_generator", server_default="document_generator"` |
| T-INFRA-06 | ✅ DONE | Updated `test_middleware.py:83` (`test_default_role_is_user` → `test_default_role_is_document_generator`); updated `tenant.py:44` fallback `"user"` → `"document_generator"` |

### TDD Evidence

| Task | Group | RED | GREEN |
|------|-------|-----|-------|
| T-INFRA-01 | A | — (verification only) | `010` is latest, `011` slot free |
| T-INFRA-04 | A | 2 FAIL (`col.default.arg == 'user'`) | 2 PASS after T-INFRA-05 |
| T-INFRA-05 | A | — | Both defaults → `document_generator`, all GREEN |
| T-INFRA-02 | B | 9 FAIL (`FileNotFoundError: 011_role_expansion.py`) | 9 PASS after T-INFRA-03 |
| T-INFRA-03 | B | — | Migration created with correct ADR-ROLE-02 order; `alembic upgrade head` applied; DB at 011 head |
| T-INFRA-06 | C | 1 FAIL (`'user' != 'document_generator'`) | 1 PASS + all 13 middleware tests GREEN |

### Files Changed

| File | Action | What |
|------|--------|------|
| `backend/src/app/infrastructure/persistence/models/user.py` | Modified | `default="user"` → `"document_generator"`, `server_default="user"` → `"document_generator"` (line 19) |
| `backend/src/app/presentation/middleware/tenant.py` | Modified | `payload.get("role", "user")` → `payload.get("role", "document_generator")` (line 44) |
| `backend/alembic/versions/011_role_expansion.py` | Created | Migration `revision="011"`, `down_revision="010"` — UPDATE before ALTER (ADR-ROLE-02); lossy downgrade documented |
| `backend/tests/unit/infrastructure/test_user_model_defaults.py` | Created | 2 tests for `UserModel.role` `default` and `server_default` (T-INFRA-04) |
| `backend/tests/integration/test_role_migration.py` | Created | 9 tests: metadata (revision/down_revision/docstring), upgrade order (execute→alter_column), downgrade order (alter_column→execute), SQL content |
| `backend/tests/unit/test_middleware.py` | Modified | Renamed `test_default_role_is_user` → `test_default_role_is_document_generator`; updated assertion from `"user"` to `"document_generator"` (line 83, W-1 from Phase 1 verify) |
| `openspec/changes/roles-expansion/tasks.md` | Modified | Marked T-INFRA-01..06 with ✅ |

### Tests Added

- `test_user_model_defaults.py`: **2 new test methods** (T-INFRA-04)
- `test_role_migration.py`: **9 new test methods** (T-INFRA-02) — 3 metadata + 3 upgrade order + 3 downgrade order

Total new tests in Phase 2: **11**

### Tests Modified

- `test_middleware.py`: renamed + updated 1 test (W-1 fix from Phase 1 verify report)

### Migration Apply Evidence

- **Alembic current**: `011 (head)` — confirmed via `alembic current`
- **Column default**: `role character varying(20) NOT NULL DEFAULT 'document_generator'::character varying` — confirmed via `\d users`
- **Row state**: 2 admin rows (`admin@sigdoc.local`, `devrafaseros@gmail.com`) — no `user` rows existed pre-migration, so no `template_creator` rows created (correct)
- **New inserts**: will default to `document_generator`

### Final Test Count

**506 passing, 0 failing** (Phase 1 baseline: 495; Phase 2 net: +11 new, 0 regressions)

---

## Phase 3 — Application Service / Auth Flow (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-APP-01 | ✅ DONE | Created `test_auth_refresh_role.py` — SCEN-ROLE-06: promoted user gets updated role in new access token |
| T-APP-02 | ✅ DONE | Added SCEN-ROLE-07 to `test_auth_refresh_role.py` — deleted user → 401 |
| T-APP-03 | ✅ DONE | Modified `/auth/refresh` handler: DB re-fetch for user, `role=user.role` from DB, 401 for missing/inactive |

### TDD Evidence

| Task | RED | GREEN |
|------|-----|-------|
| T-APP-01 | FAIL — handler returned role='user' (fallback default) not 'template_creator' from DB | PASS after T-APP-03 |
| T-APP-02 | FAIL — HTTP 200 not 401 (no user-existence check) | PASS after T-APP-03 |
| T-APP-03 | — | Both T-APP-01 and T-APP-02 GREEN |

### Files Changed

| File | Action | What |
|------|--------|------|
| `backend/src/app/presentation/api/v1/auth.py` | Modified | `/auth/refresh` handler: DB user re-fetch, `role=user.role`, HTTP 401 for missing/inactive |
| `backend/tests/integration/test_auth_refresh_role.py` | Created | 2 integration tests: SCEN-ROLE-06 (promoted user role), SCEN-ROLE-07 (deleted user 401) |
| `backend/tests/integration/test_auth_api.py` | Modified | `test_refresh_with_valid_token_returns_200` updated to monkeypatch SQLAlchemyUserRepository |

### Tests Added

- `test_auth_refresh_role.py`: **2 new test methods**

### Final Test Count

**508 passing, 0 failing** (Phase 2 baseline: 506; Phase 3 net: +2 new, 0 regressions)

---

## Phase 4 — Presentation (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-PRES-01 | ✅ DONE | Created `test_role_validation.py` — 7 unit tests for UpdateUserRequest schema |
| T-PRES-02 | ✅ DONE | Updated `UpdateUserRequest.validate_role` allow-list to 3-role set |
| T-PRES-03 | ✅ DONE | Extended `test_users_api.py` — `POST /users` without role → `document_generator` |
| T-PRES-04 | ✅ DONE | Updated `users.py:65` — explicit `role="document_generator"` |
| T-PRES-05 | ✅ DONE | Added `require_template_manager = require_capability(can_manage_own_templates)` to `dependencies.py` |
| T-PRES-06 | ✅ DONE | Created `test_template_endpoint_gates.py` — `document_generator` → upload → 403 |
| T-PRES-07 | ✅ DONE | `template_creator` → upload → 201 |
| T-PRES-08 | ✅ DONE | `admin` → upload → 201; `document_generator` → versions → 403; `template_creator` → versions → 201 |
| T-PRES-09 | ✅ DONE | Wired `Depends(require_template_manager)` on `POST /templates/upload` and `POST /templates/{id}/versions` |
| T-PRES-10 | ✅ DONE | `document_generator` + shared → 201; + non-shared → 403 (service layer) |

### TDD Evidence

| Task | RED | GREEN |
|------|-----|-------|
| T-PRES-01 | 4 FAIL (new roles not accepted; user not rejected) | 7 PASS after T-PRES-02 |
| T-PRES-02 | — | 3-role allow-list set; all 7 unit tests GREEN |
| T-PRES-03 | 1 FAIL (role was 'user') | 1 PASS after T-PRES-04 |
| T-PRES-04 | — | `users.py:65` → `document_generator`; 8 users tests GREEN |
| T-PRES-05 | — | `require_template_manager` added; behavior covered by T-PRES-06..10 |
| T-PRES-06 | 1 FAIL (got 201, expected 403 — no gate) | PASS after T-PRES-09 |
| T-PRES-07..10 | Some gates via service layer already; some needed T-PRES-09 | All 7 gate tests GREEN after T-PRES-09 |

### Files Changed

| File | Action | What |
|------|--------|------|
| `backend/src/app/presentation/schemas/user.py` | Modified | `validate_role` allow-list → `("admin", "template_creator", "document_generator")` |
| `backend/src/app/presentation/api/v1/users.py` | Modified | `role="user"` → `role="document_generator"` (line 65) |
| `backend/src/app/presentation/api/dependencies.py` | Modified | Added `require_template_manager = require_capability(can_manage_own_templates)` |
| `backend/src/app/presentation/api/v1/templates.py` | Modified | `POST /templates/upload` and `POST /templates/{id}/versions` → `Depends(require_template_manager)` |
| `backend/tests/unit/presentation/test_role_validation.py` | Created | 7 unit tests for UpdateUserRequest role validation |
| `backend/tests/integration/test_users_api.py` | Modified | +1 test (SCEN-ROLE-05) + 8 fixture role migrations (`user` → `document_generator`) |
| `backend/tests/integration/test_templates_api.py` | Modified | 5 fixture role migrations |
| `backend/tests/integration/test_template_endpoint_gates.py` | Created | 7 integration tests: SCEN-TMP-02..08 |

### Tests Added

- `test_role_validation.py` (NEW): **7 new unit tests** (T-PRES-01)
- `test_users_api.py`: **1 new integration test** (T-PRES-03)
- `test_template_endpoint_gates.py` (NEW): **7 new integration tests** (T-PRES-06..10)

Total new tests in Phase 4: **15**

### Final Test Count

**523 passing, 0 failing** (Phase 3 baseline: 508; Phase 4 net: +15 new, 0 regressions)

---

## Phase 5 — Frontend (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-FE-01 | ✅ DONE | Created `permissions.ts` with `Role` type and 4 capability helpers |
| T-FE-02 | ✅ DONE | Created `role-labels.ts` with `ROLE_LABELS` + `getRoleLabel` (name deviates from ADR `roleLabel` — cosmetic) |
| T-FE-03 | ✅ DONE | Wrapped `<UploadTemplateDialog />` with `{canUploadTemplates(user?.role) && ...}` |
| T-FE-04 | ✅ DONE | `EditUserDialog` expanded to 3 role options via `ROLE_LABELS`; legacy `"user"` removed |
| T-FE-05 | ✅ DONE | Added `<Badge variant="secondary" className="text-xs">{getRoleLabel(user?.role)}</Badge>` to authenticated header |
| T-FE-06 | ✅ DONE | Read-only verification — `/users` and `/audit` guarded by `{isAdmin && ...}`; `/usage` open to all (intentional) |

### Files Changed

| File | Action | What |
|------|--------|------|
| `frontend/src/shared/lib/permissions.ts` | Created | `Role` type + `canUploadTemplates`, `canManageUsers`, `canViewAudit`, `canViewTenantUsage` |
| `frontend/src/shared/lib/role-labels.ts` | Created | `ROLE_LABELS: Record<Role, string>` + `getRoleLabel` helper with `"Usuario"` fallback |
| `frontend/src/routes/_authenticated/templates/index.tsx` | Modified | `UploadTemplateDialog` gated with `canUploadTemplates(user?.role)` (line 42) |
| `frontend/src/features/users/components/EditUserDialog.tsx` | Modified | 3 `SelectItem` options via `ROLE_LABELS`; `"user"` removed; fallback `?? "document_generator"` |
| `frontend/src/routes/_authenticated.tsx` | Modified | Role badge `<Badge variant="secondary" className="text-xs">{getRoleLabel(user?.role)}</Badge>` in header |

### Tests Added

None (no frontend test runner — typecheck + lint only per ADR-TEST-01)

### Frontend Check Results

- `npx tsc --noEmit -p tsconfig.app.json`: **0 errors**
- `npm run lint`: **0 errors, 4 warnings** (pre-existing baseline)

### Final Test Count

**523 passing, 0 failing** (Phase 4 baseline: 523; Phase 5 net: 0 new backend tests, 0 regressions)

---

## Phase 6 — Regression Gate (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-REG-01 | ✅ DONE | Extended truth table (8 cases → 10) + 2 new standalone tests; updated `DOWNLOAD_FORMAT_PERMISSIONS`: `"user"` removed, `"template_creator"` + `"document_generator"` added explicitly |
| T-REG-02 | ✅ DONE | Full suite: 527 passing, 0 failing — 3 consecutive stable runs |
| T-REG-03 | ✅ DONE | TypeScript: 0 errors; Lint: 0 errors, 4 warnings (pre-existing baseline) |

### TDD Evidence (T-REG-01)

| Task | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-------|------------|-----|-------|-------------|----------|
| T-REG-01 | Unit | ✅ 6/6 | ✅ `test_download_format_permissions_dict_contains_new_roles` FAILED (`template_creator` not in dict; `"user"` still present) | ✅ All 10 PASS after removing `"user"` and adding `template_creator`/`document_generator` to dict | ✅ 3 test functions (truth table, legacy-user PDF-only, dict membership) | ✅ Docstring updated with roles-expansion note |

### DOWNLOAD_FORMAT_PERMISSIONS Audit (T-REG-01)

**Finding**: The `"user"` key was present in `DOWNLOAD_FORMAT_PERMISSIONS` — a stale legacy entry from before the roles-expansion migration. The `can_download_format` function already handled unknown roles via the safe-default `frozenset({"pdf"})`, so the `"user"` entry was effectively redundant but misleading.

**Action taken**:
- Removed `"user": frozenset({"pdf"})` from the dict
- Added explicit `"template_creator": frozenset({"pdf"})` and `"document_generator": frozenset({"pdf"})`
- Updated module docstring to explain the absence of `"user"` and the safe-default behavior

**Behavior preserved**: `can_download_format("user", "pdf")` still returns `True` (via safe-default); `can_download_format("user", "docx")` still returns `False`. The behavioral contract is unchanged — only the implementation clarity improved.

**Truth table (final)**:

| Role | docx | pdf |
|------|------|-----|
| `admin` | True | True |
| `template_creator` | False | True |
| `document_generator` | False | True |
| `"user"` (legacy/unknown) | False | True (safe-default) |
| any unknown | False | True (safe-default) |

### Files Changed

| File | Action | What |
|------|--------|------|
| `backend/src/app/domain/services/document_permissions.py` | Modified | Removed `"user"` key; added `template_creator` + `document_generator` entries; updated docstring |
| `backend/tests/unit/domain/test_document_permissions.py` | Modified | Expanded truth table (6 → 8 parametrized cases); added `test_legacy_user_role_resolves_to_pdf_only` and `test_download_format_permissions_dict_contains_new_roles` |
| `openspec/changes/roles-expansion/tasks.md` | Modified | Marked T-REG-01, T-REG-02, T-REG-03 with ✅ |

### Tests Added

- `test_document_permissions.py`: +4 new (2 new parametrized rows for `template_creator` and `document_generator` → 2 new; 2 new standalone test functions)
  - Net: **+4 new test cases** (6 parametrized → 8 parametrized = +2 instances; +2 standalone = +4 total)

### Final Test Count

**527 passing, 0 failing** (Phase 5 baseline: 523; Phase 6 net: +4 new, 0 regressions)
3 consecutive runs: 527 / 527 / 527 — deterministic.

---

## Phase 7 — Operational (COMPLETE)

### Tasks

| Task | Status | Notes |
|------|--------|-------|
| T-OPS-01 | ✅ DONE | No new production deps: `pyproject.toml` and `package.json` unchanged; `backend/.env.example` unchanged |
| T-OPS-02 | ✅ DONE | Added "Role model" section to `backend/README.md` (inserted before "Architecture" section) |

### T-OPS-01 — Dependency Audit

- `backend/pyproject.toml`: **unchanged** — `git diff HEAD` shows no modifications. No new prod or dev deps added.
- `frontend/package.json`: **unchanged** — `git diff HEAD` shows no modifications.
- `backend/.env.example`: **unchanged** — `git diff HEAD` shows no modifications. No new env vars required (`GOTENBERG_URL`, `GOTENBERG_TIMEOUT`, `ADMIN_PASSWORD` remain the same set).

**Result**: No `docker compose build api` required. No new env var documentation needed.

### T-OPS-02 — README Update

Added a new "Role model" section to `backend/README.md` between the existing content and the "Architecture" section:

- Table of 3 roles with capabilities and download format columns
- Default role documentation (`document_generator`)
- Key helpers in `domain/services/permissions.py` and `presentation/api/dependencies.py`
- Migration `011_role_expansion.py` ordering caveat (UPDATE before ALTER DEFAULT in upgrade; reverse in downgrade; lossy downgrade warning)
- Download format permissions note (legacy `"user"` key absent; safe-default behavior)

### Files Changed

| File | Action | What |
|------|--------|-------|
| `backend/README.md` | Modified | Added "Role model" section (~30 lines) before "Architecture" |
| `openspec/changes/roles-expansion/tasks.md` | Modified | Marked T-OPS-01, T-OPS-02 with ✅ |

---

## OVERALL COMPLETION SUMMARY

| Phase | Tasks | Status | Tests added | Final count |
|-------|-------|--------|-------------|-------------|
| Phase 1 — Domain | 6 | ✅ COMPLETE | +22 | 495 |
| Phase 2 — Infrastructure | 6 | ✅ COMPLETE | +11 | 506 |
| Phase 3 — Auth Flow | 3 | ✅ COMPLETE | +2 | 508 |
| Phase 4 — Presentation | 10 | ✅ COMPLETE | +15 | 523 |
| Phase 5 — Frontend | 6 | ✅ COMPLETE | 0 (no runner) | 523 |
| Phase 6 — Regression Gate | 3 | ✅ COMPLETE | +4 | 527 |
| Phase 7 — Operational | 2 | ✅ COMPLETE | 0 | 527 |
| **Total** | **36** | **✅ ALL COMPLETE** | **+54** | **527** |

**Frontend**: TypeScript 0 errors, Lint 0 errors / 4 warnings (pre-existing).
**Backend**: 527/527 passing, 0 failing, deterministic (3-run stability confirmed).
**All 36 tasks marked ✅.**
