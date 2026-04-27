# Proposal: roles-expansion

## Why

Sigdoc serves regulated medical clinics that need granular control over who can publish (template authors) versus who can only consume (document operators). The current 2-role model collapses both responsibilities into `user`, which forces tenants to either over-trust everyone or hand-edit DB rows. Splitting `user` into `template_creator` and `document_generator` delivers a 3-tier least-privilege model. The recent RBAC consolidation (`permissions.py` as single source of truth, `require_capability` pattern) makes the expansion mechanical: extend helpers, add 2 new ones, gate 2 endpoints, conditionally render 1 component.

## What Changes

- 3-role taxonomy: `admin`, `template_creator`, `document_generator`
- Data migration: existing `user` → `template_creator` (1:1)
- New default for admin-created users: `document_generator` (least privilege)
- 2 new permission helpers + 2 endpoint gates (template upload, version creation)
- Fix pre-existing JWT refresh role bug (refresh returns `"user"` regardless of actual role)
- Frontend: hide upload UI for `document_generator`, expand role Select, add Spanish role labels
- Schema validators accept the 3 role names, reject any other

## Out of Scope

- Role hierarchy / inheritance system
- Per-template fine-grained ACL (sharing model already covers this)
- Per-user override capability flags
- Role-based rate limiting tiers
- Self-service role-request UI
- Custom roles per tenant
- Audit log entries for role changes (existing `audit_log` already covers user mutations)

## Decisions

**D-01 — JWT refresh role propagation (CRITICAL).** Adopt option (b): `/auth/refresh` re-fetches the user from DB and emits the access token with `user.role`. Single source of truth, role revocations take effect on refresh, no token-vs-DB desync, no migration ambiguity. Cost: one indexed PK lookup per refresh — negligible.

**D-02 — Permission helper expansion.** Keep per-role bool helpers (current pattern). Same shape as `document_permissions.py`'s frozen dict. 3 roles is below the complexity threshold for a capability matrix; matrix migration stays mechanical if we ever cross 5+ roles.

**D-03 — New helper shape.** Single helper `can_manage_own_templates(role) -> bool` returning True for `admin` + `template_creator`. Gates upload, new version, and any future "modify-own-templates" verb. Avoids hypothetical splits ("create new but not version existing") that no product requirement asks for. Delete/share stay ownership-gated at service layer.

**D-04 — Endpoint gating mechanism.** Define `require_template_manager = require_capability(can_manage_own_templates)` in `dependencies.py`, mirroring `require_user_manager` / `require_audit_viewer`. Apply it via `Depends(...)` to `POST /templates/upload` and `POST /templates/{id}/versions`.

**D-05 — Document generation gating.** No new helper. All 3 roles can call `POST /documents/generate` and `POST /documents/generate-bulk`; the visibility constraint lives at `template_repository` (owned + shared). `document_generator` owns nothing, so they can only generate from shared templates — capability emerges from data, not from a verb gate.

**D-06 — Migration shape (`011_role_expansion.py`).** Upgrade: `UPDATE users SET role='template_creator' WHERE role='user'` then `ALTER TABLE users ALTER COLUMN role SET DEFAULT 'document_generator'`. Downgrade: collapse both new roles back to `'user'` and restore the old default — lossy but acceptable. Column is already `String(20)`; no `ALTER TYPE` needed.

**D-07 — Entity/model/schema defaults.**
- `domain/entities/user.py` line 13: `role: str = "document_generator"`
- `infrastructure/persistence/models/user.py` line 19: `default="document_generator"`, `server_default="document_generator"`
- `presentation/schemas/user.py` `validate_role`: accept `{"admin", "template_creator", "document_generator"}`, 422 otherwise
- `signup_service.py` first-user `role="admin"` UNCHANGED (explicit set, not a default)

**D-08 — Frontend role-aware UI.** New file `frontend/src/shared/lib/permissions.ts` mirrors backend names (`canManageOwnTemplates`, `canManageUsers`, etc.) — single FE source of truth. Wrap `<UploadTemplateDialog />` render with `canManageOwnTemplates(user.role)`. Add a small role-badge pill in the authenticated header so users see why the UI looks the way it does.

**D-09 — Spanish labels.** Single export `ROLE_LABELS` in `frontend/src/shared/lib/role-labels.ts`:
- `admin` → "Administrador"
- `template_creator` → "Creador de plantillas"
- `document_generator` → "Generador de documentos"
Used in `EditUserDialog` Select, user-list table, and the header badge.

**D-10 — Test scope.** Extend `test_permissions.py` truth tables (3 roles + unknown × every helper); new `test_role_validation.py` for schema acceptance/rejection; migration test (upgrade + downgrade round-trip on a seeded DB) modeled after `pdf-export`'s T-INT-04; endpoint integration tests per role × per gated endpoint expecting 200/403; refresh-token test asserting role comes from DB, not the token claim.

## Module Map

| File | Action |
|---|---|
| `backend/alembic/versions/011_role_expansion.py` | NEW |
| `backend/src/app/domain/services/permissions.py` | MODIFY (extend 7 helpers, add `can_manage_own_templates`) |
| `backend/src/app/domain/services/document_permissions.py` | MODIFY (3-role rows in `DOWNLOAD_FORMAT_PERMISSIONS`) |
| `backend/src/app/domain/entities/user.py` | MODIFY (default `"document_generator"`) |
| `backend/src/app/infrastructure/persistence/models/user.py` | MODIFY (`default` + `server_default`) |
| `backend/src/app/presentation/schemas/user.py` | MODIFY (3-role allow-list in `validate_role`) |
| `backend/src/app/presentation/api/dependencies.py` | MODIFY (add `require_template_manager`) |
| `backend/src/app/presentation/api/v1/users.py` | MODIFY (line 65 default → `"document_generator"`) |
| `backend/src/app/presentation/api/v1/templates.py` | MODIFY (gate `POST /upload`, `POST /{id}/versions`) |
| `backend/src/app/presentation/api/v1/auth.py` | MODIFY (refresh re-fetches user from DB) |
| `backend/src/app/presentation/middleware/tenant.py` | MODIFY (default role `"document_generator"`) |
| `backend/tests/unit/domain/test_permissions.py` | MODIFY |
| `backend/tests/unit/domain/test_document_permissions.py` | MODIFY |
| `backend/tests/unit/presentation/test_role_validation.py` | NEW |
| `backend/tests/integration/test_role_migration.py` | NEW |
| `backend/tests/integration/test_template_endpoint_gates.py` | NEW |
| `backend/tests/integration/test_auth_refresh_role.py` | NEW |
| `frontend/src/shared/lib/permissions.ts` | NEW |
| `frontend/src/shared/lib/role-labels.ts` | NEW |
| `frontend/src/routes/_authenticated/templates/index.tsx` | MODIFY (conditional render) |
| `frontend/src/features/users/components/EditUserDialog.tsx` | MODIFY (3-option Select with Spanish labels) |
| `frontend/src/features/users/components/UserListTable.tsx` (or equivalent) | MODIFY (display Spanish role label) |
| `frontend/src/routes/_authenticated.tsx` | MODIFY (header role-badge pill) |

## Migration Plan

`011_role_expansion.py`:
- `upgrade()`: `UPDATE users SET role='template_creator' WHERE role='user'` then `ALTER TABLE users ALTER COLUMN role SET DEFAULT 'document_generator'`. Expected affected rows: 0 in dev, N in prod (one per pre-existing non-admin user). Idempotent because the WHERE clause only matches `'user'`.
- `downgrade()`: `ALTER COLUMN role SET DEFAULT 'user'`, `UPDATE users SET role='user' WHERE role IN ('template_creator', 'document_generator')`. Lossy (collapses 2 roles into 1) — acceptable for emergency rollback only.
- Deployment order: migration → backend → frontend. After migration, no `'user'` rows exist; old code paths keying off `"user"` still match nothing (safe degradation to least-privilege).

## Success Criteria

- [ ] `alembic upgrade head` migrates a seeded `user`-row DB to `template_creator` rows; `alembic downgrade -1` reverses it
- [ ] All 9 permission helpers return the truth-table value for each of `admin` / `template_creator` / `document_generator` / unknown
- [ ] `POST /templates/upload` and `POST /templates/{id}/versions` return 403 for `document_generator`, 200 for the other two
- [ ] `POST /auth/refresh` returns an access token whose `role` matches the current DB row, not the refresh-token payload
- [ ] `validate_role` rejects any string outside the 3-role set with HTTP 422
- [ ] Frontend hides `<UploadTemplateDialog />` for `document_generator`; the Select in `EditUserDialog` offers 3 Spanish-labeled options; the role badge appears in the authenticated header
- [ ] Test suite: 473 baseline + new tests, all green

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Refresh-token bug ships unfixed → all refreshed tokens carry an invalid role | High without fix | D-01 mandates DB lookup on refresh; integration test asserts behavior |
| Stale access tokens carry old role until expiry after admin role change | Medium | Pre-existing; mitigated by short access-token TTL; documented as known limitation |
| `document_generator` calls upload via direct API (no FE) | High without backend gate | D-04 adds `require_template_manager`; integration test per-role × per-endpoint |
| Migration runs on DB with rows in unexpected role values (e.g., manual test data) | Low | Migration only touches `role='user'` rows; foreign roles untouched |
| Frontend role badge confuses users / clutters header | Low | Small unobtrusive pill; single Spanish label; behind feature consensus during design phase |
| Spanish labels diverge across components | Medium | Single `ROLE_LABELS` export consumed everywhere; lint rule via grep in CI optional |

## Spec Capabilities

Two new capabilities, split because they target distinct surfaces and will evolve independently:

- **`role-model`** — defines the 3-role taxonomy, the `user → template_creator` migration, the `document_generator` default, the `validate_role` allow-list, and the JWT refresh-from-DB contract. Lives at backend domain + auth boundary.
- **`template-management-permissions`** — defines `can_manage_own_templates`, the `require_template_manager` gate on upload + new-version endpoints, and the FE conditional render of `UploadTemplateDialog`. Lives at the template surface.

Folding into a single spec would conflate "who you are" (identity/role) with "what you can do to templates" (capability). The split mirrors the existing `permissions.py` vs `document_permissions.py` separation.

**Note for downstream phases**: Strict TDD Mode is ACTIVE. `sdd-apply` must follow strict-tdd.md (test runner: `uv run pytest` for backend, `bun test` for frontend).
