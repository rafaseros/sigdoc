# Tasks — roles-expansion

## Conventions
- Strict TDD: every implementation task MUST be preceded by a `[TEST]` task that fails first
- Task IDs: `T-<PHASE>-<NN>` (e.g., T-DOMAIN-01, T-INFRA-03)
- Each task lists: id, title, files touched, REQs/ADRs satisfied, dependencies
- A task is DONE when: code written, related tests pass, no regressions
- Test runner (backend): `docker compose -f docker/docker-compose.yml exec -T api pytest <args>`
- Test runner (frontend): typecheck `bun run tsc --noEmit`, lint `bun run lint`

---

## Phase 1 — Domain & Permissions

### T-DOMAIN-01: [TEST] Extend truth tables for all existing permission helpers with `template_creator` and `document_generator` rows ✅
- **Files**: `backend/tests/unit/domain/test_permissions.py`
- **REQs/ADRs**: REQ-ROLE-01
- **Depends on**: —
- **Description**: Add rows for `template_creator` and `document_generator` to every existing truth-table parametrize in `test_permissions.py` (e.g., `can_manage_users`, `can_view_audit`, `can_download_documents`). All new rows must assert the expected False/True values. These tests must FAIL before T-DOMAIN-02 makes them pass.

### T-DOMAIN-02: Update all existing permission helpers to handle `template_creator` and `document_generator` explicitly ✅
- **Files**: `backend/src/app/domain/services/permissions.py`
- **REQs/ADRs**: REQ-ROLE-01, ADR-TMP-01
- **Depends on**: T-DOMAIN-01
- **Description**: Audit every helper in `permissions.py` (`can_manage_users`, `can_view_audit`, etc.) — ensure none implicitly falls through with `"user"` logic. Both new roles should return False for admin-only capabilities. Make T-DOMAIN-01 tests pass.

### T-DOMAIN-03: [TEST] Truth table for `can_manage_own_templates` — four inputs (admin/template_creator/document_generator/unknown) ✅
- **Files**: `backend/tests/unit/domain/test_permissions.py`
- **REQs/ADRs**: REQ-TMP-01, SCEN-TMP-01
- **Depends on**: T-DOMAIN-02
- **Description**: Add a parametrized test asserting `can_manage_own_templates` returns `True` for `admin` and `template_creator`, `False` for `document_generator` and any unknown string. Must FAIL before T-DOMAIN-04.

### T-DOMAIN-04: Implement `can_manage_own_templates(role: str) -> bool` in permissions.py ✅
- **Files**: `backend/src/app/domain/services/permissions.py`
- **REQs/ADRs**: REQ-TMP-01, ADR-TMP-01
- **Depends on**: T-DOMAIN-03
- **Description**: Add `can_manage_own_templates` next to existing helpers; add to `__all__`. Returns `True` for `{"admin", "template_creator"}`, `False` otherwise (safe-default deny). Make T-DOMAIN-03 pass.

### T-DOMAIN-05: [TEST] `User` entity default role = `document_generator` when instantiated without `role` arg ✅
- **Files**: `backend/tests/unit/domain/test_user_entity.py` (NEW — dedicated entity test)
- **REQs/ADRs**: REQ-ROLE-04, SCEN-ROLE-09, ADR-ROLE-03
- **Depends on**: T-DOMAIN-02
- **Description**: Add a unit test: `User()` (no `role` arg) → `instance.role == "document_generator"`. Must FAIL before T-DOMAIN-06.

### T-DOMAIN-06: Update `User` domain entity default role to `document_generator` ✅
- **Files**: `backend/src/app/domain/entities/user.py` (line 13)
- **REQs/ADRs**: REQ-ROLE-04, ADR-ROLE-03
- **Depends on**: T-DOMAIN-05
- **Description**: Change the `role` field default from `"user"` to `"document_generator"`. Make T-DOMAIN-05 pass.

---

## Phase 2 — Infrastructure (DB Migration + ORM Model)

### T-INFRA-01: Verify migration slot — confirm `010` is latest and `011` is free ✅
- **Files**: `backend/alembic/versions/` (read-only verification)
- **REQs/ADRs**: ADR-ROLE-02
- **Depends on**: —
- **Description**: Run `ls backend/alembic/versions/` and confirm `010_pdf_export.py` is the latest migration and no `011_*.py` file exists. This is a verification step; no file is created yet. Document `down_revision="010"` as the correct value.

### T-INFRA-02: [TEST] Migration round-trip integration test — upgrade transforms `user` rows; downgrade reverses ✅
- **Files**: `backend/tests/integration/test_role_migration.py` (NEW)
- **REQs/ADRs**: REQ-ROLE-02, REQ-ROLE-03, SCEN-ROLE-01, SCEN-ROLE-02
- **Depends on**: T-INFRA-01
- **Description**: Create `test_role_migration.py`. Seed DB with roles `['admin', 'user', 'user']`. Call `upgrade()` function directly. Assert roles are `['admin', 'template_creator', 'template_creator']`. Then call `downgrade()`. Assert roles collapse to `['admin', 'user', 'user']` and server default reverts. Must FAIL (file missing) before T-INFRA-03 creates the migration.

### T-INFRA-03: Implement Alembic migration `011_role_expansion.py` ✅
- **Files**: `backend/alembic/versions/011_role_expansion.py` (NEW)
- **REQs/ADRs**: REQ-ROLE-02, REQ-ROLE-03, ADR-ROLE-02
- **Depends on**: T-INFRA-02
- **Description**: Create migration with `revision="011"`, `down_revision="010"`. `upgrade()`: first `UPDATE users SET role='template_creator' WHERE role='user'`, then `ALTER COLUMN role SET DEFAULT 'document_generator'` (order is critical per ADR-ROLE-02). `downgrade()`: reverse default first, then collapse both new roles to `'user'` (lossy — document in docstring). Make T-INFRA-02 pass.

### T-INFRA-04: [TEST] Verify `UserModel.role` defaults — Python-side `default` and DB-side `server_default` both equal `document_generator` ✅
- **Files**: `backend/tests/unit/infrastructure/` (or extend an existing model test)
- **REQs/ADRs**: REQ-ROLE-05, ADR-ROLE-03
- **Depends on**: T-INFRA-01
- **Description**: Add a unit test inspecting the `UserModel.role` column's `default` and `server_default` kwargs — assert both equal `"document_generator"`. Must FAIL before T-INFRA-05.

### T-INFRA-05: Update `UserModel.role` column defaults in `user.py` ✅
- **Files**: `backend/src/app/infrastructure/persistence/models/user.py` (line 19)
- **REQs/ADRs**: REQ-ROLE-05, ADR-ROLE-03
- **Depends on**: T-INFRA-04
- **Description**: Set `default="document_generator"` and `server_default="document_generator"` on the `role` column. Make T-INFRA-04 pass.

### T-INFRA-06: Update `tenant.py` middleware safe-default role from `"user"` to `"document_generator"` ✅
- **Files**: `backend/src/app/presentation/middleware/tenant.py` (line 44)
- **REQs/ADRs**: ADR-ROLE-03
- **Depends on**: T-DOMAIN-02
- **Description**: Change `role=payload.get("role", "user")` to `role=payload.get("role", "document_generator")`. This ensures stale tokens with no role claim degrade to least privilege (document_generator, which is denied template management). No separate test needed — existing middleware tests cover the path; verify they still pass.

---

## Phase 3 — Application Service / Auth Flow

### T-APP-01: [TEST] `/auth/refresh` re-fetches role from DB — promoted user gets updated role in new access token ✅
- **Files**: `backend/tests/integration/test_auth_refresh_role.py` (NEW)
- **REQs/ADRs**: REQ-ROLE-09, SCEN-ROLE-06, ADR-ROLE-01
- **Depends on**: T-INFRA-03, T-DOMAIN-06
- **Description**: Create `test_auth_refresh_role.py`. Scenario: create `document_generator` user + refresh token; admin promotes to `template_creator`; user calls `POST /auth/refresh`; assert new access token decodes to `role="template_creator"`. Must FAIL before T-APP-02.

### T-APP-02: [TEST] `/auth/refresh` returns 401 for deleted user ✅
- **Files**: `backend/tests/integration/test_auth_refresh_role.py`
- **REQs/ADRs**: REQ-ROLE-10, SCEN-ROLE-07, ADR-ROLE-01
- **Depends on**: T-APP-01
- **Description**: Add scenario: user holds valid refresh token; admin deletes user from DB; user calls `POST /auth/refresh`; assert HTTP 401 and no access token issued. Must FAIL before T-APP-03.

### T-APP-03: Modify `/auth/refresh` handler to re-fetch user from DB ✅
- **Files**: `backend/src/app/presentation/api/v1/auth.py` (near line 147)
- **REQs/ADRs**: REQ-ROLE-09, REQ-ROLE-10, ADR-ROLE-01
- **Depends on**: T-APP-01, T-APP-02
- **Description**: After decoding the refresh token and validating `type="refresh"`, extract `sub`, call `user_repository.get_by_id(UUID(sub))`. If `None` or `is_active=False`, raise HTTP 401. Use `user.role` (from DB) — NOT `payload.get("role", ...)` — when minting the new access token. Make T-APP-01 and T-APP-02 pass.

---

## Phase 4 — Presentation (Gates, Schemas, Default-on-Create)

### T-PRES-01: [TEST] Schema validation — `UpdateUserRequest` rejects `role="user"` with 422 ✅
- **Files**: `backend/tests/unit/presentation/test_role_validation.py` (NEW)
- **REQs/ADRs**: REQ-ROLE-06, SCEN-ROLE-04, ADR-ROLE-04
- **Depends on**: T-DOMAIN-02
- **Description**: Create `test_role_validation.py`. Add parametrized test: `role="user"` → `ValidationError`; `role="invalid"` → `ValidationError` with message naming the 3 allowed values (SCEN-ROLE-10); `role="document_generator"` → valid (SCEN-ROLE-03). Must FAIL before T-PRES-02.

### T-PRES-02: Update `UpdateUserRequest.validate_role` to accept 3-role set only ✅
- **Files**: `backend/src/app/presentation/schemas/user.py` (line 33)
- **REQs/ADRs**: REQ-ROLE-06, ADR-ROLE-04
- **Depends on**: T-PRES-01
- **Description**: Replace `("admin", "user")` allow-list with `("admin", "template_creator", "document_generator")`. Update the 422 error message to name all three. Do NOT add a `role` field to `CreateUserRequest`. Make T-PRES-01 pass.

### T-PRES-03: [TEST] `POST /users` without `role` field → 201 with `role="document_generator"` ✅
- **Files**: `backend/tests/integration/test_users_api.py`
- **REQs/ADRs**: REQ-ROLE-08, SCEN-ROLE-05, ADR-ROLE-05
- **Depends on**: T-PRES-02, T-INFRA-05
- **Description**: Extend `test_users_api.py` with a test: admin POSTs `/users` with no `role` field; assert 201 and `response["role"] == "document_generator"`. Must FAIL before T-PRES-04.

### T-PRES-04: Update `POST /users` handler — set default role to `document_generator` explicitly ✅
- **Files**: `backend/src/app/presentation/api/v1/users.py` (line 65)
- **REQs/ADRs**: REQ-ROLE-08, ADR-ROLE-05
- **Depends on**: T-PRES-03
- **Description**: Change literal `role="user"` in the User construction to `role="document_generator"`. Explicit assignment (not Pydantic default) keeps policy visible. Make T-PRES-03 pass.

### T-PRES-05: Add `require_template_manager` dependency to `dependencies.py` ✅
- **Files**: `backend/src/app/presentation/api/dependencies.py`
- **REQs/ADRs**: REQ-TMP-02, ADR-TMP-02
- **Depends on**: T-DOMAIN-04
- **Description**: Add `require_template_manager = require_capability(can_manage_own_templates)`, mirroring `require_user_manager` and `require_audit_viewer`. Import `can_manage_own_templates` from `domain/services/permissions.py`. No separate test needed — behavior covered by T-PRES-06 through T-PRES-10.

### T-PRES-06: [TEST] `document_generator` → `POST /templates/upload` returns 403 ✅
- **Files**: `backend/tests/integration/test_template_endpoint_gates.py` (NEW)
- **REQs/ADRs**: REQ-TMP-03, SCEN-TMP-02, ADR-TMP-03
- **Depends on**: T-PRES-05
- **Description**: Create `test_template_endpoint_gates.py`. Test: authenticate as `document_generator`; call `POST /templates/upload` with a valid `.docx`; assert 403. Must FAIL before T-PRES-09 wires the gate.

### T-PRES-07: [TEST] `template_creator` → `POST /templates/upload` returns 201 ✅
- **Files**: `backend/tests/integration/test_template_endpoint_gates.py`
- **REQs/ADRs**: REQ-TMP-03, SCEN-TMP-03, ADR-TMP-03
- **Depends on**: T-PRES-06
- **Description**: Add test: authenticate as `template_creator`; call `POST /templates/upload`; assert 201. Must FAIL before T-PRES-09.

### T-PRES-08: [TEST] `admin` → `POST /templates/upload` returns 201; `document_generator` → `POST /templates/{id}/versions` returns 403; `template_creator` → `POST /templates/{id}/versions` on owned template returns 201 ✅
- **Files**: `backend/tests/integration/test_template_endpoint_gates.py`
- **REQs/ADRs**: REQ-TMP-03, REQ-TMP-04, SCEN-TMP-04, SCEN-TMP-05, SCEN-TMP-06, ADR-TMP-03
- **Depends on**: T-PRES-07
- **Description**: Add three scenarios: admin upload (201), document_generator version (403), template_creator version own template (201). Must FAIL before T-PRES-09.

### T-PRES-09: Wire `Depends(require_template_manager)` to `POST /templates/upload` and `POST /templates/{id}/versions` ✅
- **Files**: `backend/src/app/presentation/api/v1/templates.py` (lines 94, 156)
- **REQs/ADRs**: REQ-TMP-03, REQ-TMP-04, ADR-TMP-03
- **Depends on**: T-PRES-05, T-PRES-08
- **Description**: Replace `get_current_user` dep with `require_template_manager` on both `POST /templates/upload` (line 94) and `POST /templates/{template_id}/versions` (line 156). The handler still receives `CurrentUser` — `require_template_manager` returns it. Make T-PRES-06, T-PRES-07, T-PRES-08 pass.

### T-PRES-10: [TEST] `document_generator` generates from shared template → 201; from non-shared → 403 ✅
- **Files**: `backend/tests/integration/test_template_endpoint_gates.py`
- **REQs/ADRs**: REQ-TMP-05, SCEN-TMP-07, SCEN-TMP-08
- **Depends on**: T-PRES-09
- **Description**: Add two scenarios: document_generator + shared template → `POST /documents/generate` → 201; document_generator + non-shared template → 403 (from service layer `TemplateAccessDeniedError`). No endpoint change needed; these tests confirm existing behavior is preserved.

---

## Phase 5 — Frontend

### T-FE-01: Create `frontend/src/shared/lib/permissions.ts` — `Role` type + capability helpers ✅
- **Files**: `frontend/src/shared/lib/permissions.ts` (NEW)
- **REQs/ADRs**: REQ-TMP-06, ADR-FE-01
- **Depends on**: —
- **Description**: Export `Role = "admin" | "template_creator" | "document_generator"`. Export `canUploadTemplates`, `canManageUsers`, `canViewAudit`, `canViewTenantUsage` mirroring backend logic. Add comment pointing to `domain/services/permissions.py` as the authoritative source.

### T-FE-02: Create `frontend/src/shared/lib/role-labels.ts` — `ROLE_LABELS` + `roleLabel` helper ✅
- **Files**: `frontend/src/shared/lib/role-labels.ts` (NEW)
- **REQs/ADRs**: REQ-TMP-08, ADR-FE-02
- **Depends on**: T-FE-01
- **Description**: Export `ROLE_LABELS: Record<Role, string>` with Spanish mappings (`admin` → `"Administrador"`, `template_creator` → `"Creador de plantillas"`, `document_generator` → `"Generador de documentos"`). Export `roleLabel(r: string | undefined): string` with `"Usuario"` fallback for unknown/undefined roles.

### T-FE-03: Wrap `<UploadTemplateDialog />` with `canUploadTemplates(user?.role)` conditional in templates page ✅
- **Files**: `frontend/src/routes/_authenticated/templates/index.tsx` (line 39)
- **REQs/ADRs**: REQ-TMP-07, SCEN-TMP-09, SCEN-TMP-10, ADR-FE-03
- **Depends on**: T-FE-01
- **Description**: Replace unconditional render with `{canUploadTemplates(user?.role) && <UploadTemplateDialog />}`. For `document_generator`, the element must be absent from the DOM entirely. For `template_creator` and `admin`, the button remains present.

### T-FE-04: Update `EditUserDialog` role `<Select>` from 2 to 3 options using `ROLE_LABELS` ✅
- **Files**: `frontend/src/features/users/components/EditUserDialog.tsx` (lines 128–129)
- **REQs/ADRs**: REQ-TMP-10, ADR-FE-03
- **Depends on**: T-FE-02
- **Description**: Expand Select options to include `admin`, `template_creator`, and `document_generator`. Use `ROLE_LABELS` for display text. Remove `"user"` from options. Set default fallback `setRole(v ?? "document_generator")` on SelectItem change.

### T-FE-05: Add role badge pill to authenticated header in `_authenticated.tsx` ✅
- **Files**: `frontend/src/routes/_authenticated.tsx` (near line 73)
- **REQs/ADRs**: REQ-TMP-09, ADR-FE-03
- **Depends on**: T-FE-02
- **Description**: Add shadcn `<Badge variant="secondary">{roleLabel(user?.role)}</Badge>` next to the email span in the authenticated layout header. Every authenticated user sees their Spanish role label on all pages.

### T-FE-06: Verify admin-only navigation tabs still gate correctly — `user?.role === "admin"` covers all non-admin roles ✅
- **Files**: `frontend/src/routes/_authenticated.tsx`
- **REQs/ADRs**: ADR-FE-04 (deferred note)
- **Depends on**: T-FE-05
- **Description**: Read-only verification — confirm `/users`, `/audit`, `/usage` nav tabs are guarded by `user?.role === "admin"`. Since neither `template_creator` nor `document_generator` equals `"admin"`, both new roles are excluded. No code change required if guard is already in place; document the finding.

---

## Phase 6 — Integration Tests + Regression Gate

### T-REG-01: [TEST] Document permissions truth table extended for `template_creator` and `document_generator` ✅
- **Files**: `backend/tests/unit/domain/test_document_permissions.py`
- **REQs/ADRs**: REQ-ROLE-01
- **Depends on**: T-DOMAIN-02
- **Description**: Extend the `DOWNLOAD_FORMAT_PERMISSIONS` truth table tests to include rows for both new roles. Also update `document_permissions.py` if any `"user"` key exists in `DOWNLOAD_FORMAT_PERMISSIONS` that must be renamed (verify in source). Must pass after T-DOMAIN-02.

### T-REG-02: Run full backend test suite — 473 baseline + N new tests, 0 failures ✅
- **Files**: `backend/` (all test files)
- **REQs/ADRs**: All REQs, D-10
- **Depends on**: T-PRES-10, T-APP-03, T-INFRA-03, T-REG-01
- **Description**: Execute `docker compose -f docker/docker-compose.yml exec -T api pytest -q`. Verify 0 failures, 0 errors. New test count is 473 + N (N = total new test functions added across all new/extended test files). Document the final count.

### T-REG-03: Frontend typecheck + lint — 0 errors ✅
- **Files**: `frontend/` (all .ts/.tsx)
- **REQs/ADRs**: ADR-FE-01, ADR-FE-02, ADR-FE-03
- **Depends on**: T-FE-06
- **Description**: Run `bun run tsc --noEmit` and `bun run lint` from `frontend/`. Both must report 0 errors. No regressions on existing TS types.

---

## Phase 7 — Operational / Docs

### T-OPS-01: Verify no new production dependencies added; flag if otherwise ✅
- **Files**: `backend/pyproject.toml`, `frontend/package.json` (read-only)
- **REQs/ADRs**: —
- **Depends on**: T-REG-02
- **Description**: Confirm neither `pyproject.toml` nor `package.json` gained new runtime deps for this change. If any were added, document them here and flag that `docker compose build api` is required. Expected result: no new deps.

### T-OPS-02: Update `backend/README.md` role taxonomy note — 3 roles, migration ordering caveat ✅
- **Files**: `backend/README.md`
- **REQs/ADRs**: —
- **Depends on**: T-REG-02
- **Description**: If `backend/README.md` documents the role model, update it to reflect 3 roles (`admin`, `template_creator`, `document_generator`). Note the migration ordering caveat: `UPDATE` must precede `ALTER DEFAULT` in `upgrade()`. If no such section exists, add a brief note under a "Role Model" heading.

---

## Estimate

| Phase | Tasks | Approx. Hours |
|---|---|---|
| Phase 1 — Domain & Permissions | 6 | ~2 h |
| Phase 2 — Infrastructure | 6 | ~3 h |
| Phase 3 — Application / Auth | 3 | ~2 h |
| Phase 4 — Presentation | 10 | ~4 h |
| Phase 5 — Frontend | 6 | ~2 h |
| Phase 6 — Regression Gate | 3 | ~1 h |
| Phase 7 — Operational | 2 | ~0.5 h |
| **Total** | **36** | **~14.5 h** |
