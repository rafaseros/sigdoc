# Exploration: roles-expansion

**Goal**: Expand the system from 2 roles (`admin`, `user`) to 3 roles (`admin`, `template_creator`, `document_generator`), migrating existing `user` rows to `template_creator` and defaulting new admin-created users to `document_generator`.

---

## Current State

The system currently has exactly 2 roles: `"admin"` and `"user"`. All permission logic is centralized in `backend/src/app/domain/services/permissions.py` (7 helpers + 1 entity predicate), introduced in a recent RBAC consolidation commit. The download format permission lives in a separate `document_permissions.py` that is re-exported by `permissions.py`.

Key facts:
- `UserModel.role` column is `String(20)` — safe for `template_creator` (16) and `document_generator` (18 chars)
- `User` entity defaults `role: str = "user"` (line 13 of `domain/entities/user.py`)
- `UserModel` defaults `role` to `"user"` in `String(20)` column (line 19 of `models/user.py`)
- `signup_service.py` hard-codes `role="admin"` for the first user (line 129) — correct, do not change
- `users.py` (admin endpoint) hard-codes `role="user"` for new users (line 65) — must change to `"document_generator"`
- Test baseline: 473 passing, 0 failing

---

## Current Role Surface (file:line)

| Location | What it does | Status |
|---|---|---|
| `backend/src/app/domain/services/permissions.py:40–96` | 7 helpers + `is_admin_role`; all return `role == "admin"` | MODIFY |
| `backend/src/app/domain/services/document_permissions.py:12–15` | `DOWNLOAD_FORMAT_PERMISSIONS` dict: `admin`→both, `user`→pdf | MODIFY |
| `backend/src/app/domain/entities/user.py:13` | `role: str = "user"` default | MODIFY |
| `backend/src/app/infrastructure/persistence/models/user.py:19` | `role` column `String(20)`, server_default `"user"` | MODIFY (server_default only; column length OK) |
| `backend/src/app/application/services/signup_service.py:129` | `role="admin"` — first user of tenant | NO CHANGE |
| `backend/src/app/presentation/api/v1/users.py:65` | `role="user"` — admin creates user | MODIFY → `"document_generator"` |
| `backend/src/app/presentation/schemas/user.py:32–35` | `validate_role` allows only `"admin"` or `"user"` | MODIFY |
| `backend/src/app/infrastructure/persistence/repositories/user_repository.py:84` | `UserModel.role == "admin"` in `count_admins_by_tenant` | NO CHANGE (intentional SQL exception) |
| `backend/src/app/presentation/api/v1/auth.py:147` | `payload.get("role", "user")` on refresh | CRITICAL BUG — see Risks |
| `backend/src/app/presentation/middleware/tenant.py:44` | `payload.get("role", "user")` JWT decode default | MODIFY default to `"document_generator"` |
| `frontend/src/shared/lib/auth.tsx:8` | `role: string` — untyped, safe | NO CHANGE |
| `frontend/src/routes/_authenticated.tsx:26` | `isAdmin = user?.role === "admin"` — nav tabs | NO CHANGE (correct for 3 roles) |
| `frontend/src/features/documents/components/DownloadButton.tsx:45` | `isAdmin = user?.role === "admin"` | NO CHANGE (correct for 3 roles) |
| `frontend/src/features/documents/components/BulkDownloadControls.tsx:11` | `isAdmin: boolean` prop passed by parent | NO CHANGE (caller uses `=== "admin"`) |
| `frontend/src/features/templates/components/TemplateList.tsx` | No role check, just renders | NO CHANGE |
| `frontend/src/features/templates/components/TemplateDetail.tsx:203,210,328` | `template.is_owner` gates Delete, Share, New Version buttons | NO CHANGE (owner-based, correct) |
| `frontend/src/routes/_authenticated/templates/index.tsx:39` | `<UploadTemplateDialog />` always visible | MODIFY — hide for `document_generator` |
| `frontend/src/features/users/components/EditUserDialog.tsx:123–130` | Role `<Select>`: only `admin` / `user` | MODIFY → 3 options |
| `frontend/src/features/users/components/CreateUserDialog.tsx` | No role field (uses backend default) | NO CHANGE (backend default changes) |

---

## Capability Matrix (3-role truth table)

### Existing helpers (post-change targets)

| Helper | admin | template_creator | document_generator | Notes |
|---|---|---|---|---|
| `can_manage_users` | True | False | False | Admin-only surface |
| `can_view_audit` | True | False | False | Admin-only surface |
| `can_view_tenant_usage` | True | False | False | Admin-only `/usage/tenant` |
| `can_view_all_documents` | True | False | False | See only own docs |
| `can_view_all_templates` | True | False | False | See owned + shared only |
| `can_include_both_formats` | True | False | False | Bulk ZIP with DOCX |
| `is_admin_role` | True | False | False | Entity-state check only |
| `can_download_format(role, "docx")` | True | False | False | PDF-only for non-admin |
| `can_download_format(role, "pdf")` | True | True | True | All roles get PDF |

### New helpers needed

| Helper | admin | template_creator | document_generator | Notes |
|---|---|---|---|---|
| `can_upload_templates` | True | True | False | Gates POST /templates/upload |
| `can_create_template_versions` | True | True | False | Gates POST /templates/{id}/versions |

**Note**: `can_modify_templates` is NOT a separate new capability. Template delete and share are already gated by `is_owner` OR `can_view_all_templates` (admin) at the `_check_access` service layer. This ownership-based model naturally works: `template_creator` uploads → becomes owner → can delete/share their own. `document_generator` never owns templates, so cannot delete/share. No new helper needed.

**Note**: `can_validate_template` and `can_autofix_template` — both `/validate` and `/auto-fix` endpoints currently accept any authenticated user. This should stay — even `document_generator` should be able to validate a template before asking a `template_creator` to upload it. No gating needed.

---

## Backend Module Map

| File | Change Type | What changes |
|---|---|---|
| `backend/alembic/versions/011_role_expansion.py` | NEW | Data migration: `user` → `template_creator`; server_default update |
| `backend/src/app/domain/services/permissions.py` | MODIFY | Extend 7 helpers + add 2 new ones (`can_upload_templates`, `can_create_template_versions`) |
| `backend/src/app/domain/services/document_permissions.py` | MODIFY | Add `template_creator` and `document_generator` entries to `DOWNLOAD_FORMAT_PERMISSIONS` |
| `backend/src/app/domain/entities/user.py` | MODIFY | Change default from `"user"` to `"document_generator"` |
| `backend/src/app/infrastructure/persistence/models/user.py` | MODIFY | Update `server_default` from `"user"` to `"document_generator"` |
| `backend/src/app/presentation/api/v1/users.py` | MODIFY | Line 65: `role="document_generator"` + import/use `can_upload_templates`/`can_create_template_versions` for template gating |
| `backend/src/app/presentation/schemas/user.py` | MODIFY | `validate_role` allow list: add `"template_creator"`, `"document_generator"` |
| `backend/src/app/presentation/api/v1/templates.py` | MODIFY | Gate `upload_template` and `upload_new_version` with `can_upload_templates`/`can_create_template_versions` |
| `backend/src/app/presentation/middleware/tenant.py` | MODIFY | Default role in JWT decode: `"user"` → `"document_generator"` (line 44) |
| `backend/src/app/presentation/api/v1/auth.py` | MODIFY | Fix refresh: fetch user from DB to get current role instead of using `payload.get("role", "user")` |
| `backend/tests/unit/domain/test_permissions.py` | MODIFY | Add `template_creator` and `document_generator` rows to all truth tables |
| `backend/tests/unit/domain/test_document_permissions.py` | MODIFY | Add `template_creator`/`document_generator` × `pdf`/`docx` cases |

---

## Frontend Module Map

| File | Change Type | What changes |
|---|---|---|
| `frontend/src/routes/_authenticated/templates/index.tsx` | MODIFY | Conditionally hide `<UploadTemplateDialog />` for `document_generator` |
| `frontend/src/features/users/components/EditUserDialog.tsx` | MODIFY | Add `template_creator` and `document_generator` options to role `<Select>` (lines 123–130) |
| `frontend/src/features/templates/components/TemplateDetail.tsx` | MODIFY | Hide "Subir Nueva Versión" button for `document_generator` who is owner (impossible by design, but guard for clarity) — or leave gated by `template.is_owner` which already works |
| `frontend/src/shared/lib/auth.tsx` | NO CHANGE | `role: string` — already untyped, no Literal constraint |
| `frontend/src/routes/_authenticated.tsx` | NO CHANGE | `isAdmin === "admin"` check remains correct |
| `frontend/src/features/documents/components/DownloadButton.tsx` | NO CHANGE | `isAdmin === "admin"` remains correct — both new roles see PDF-only |
| `frontend/src/features/documents/components/BulkDownloadControls.tsx` | NO CHANGE | Prop passed correctly from parent |

---

## Migration Strategy

### Column length — SAFE
`UserModel.role` is `String(20)`. `document_generator` is 18 chars. No `ALTER COLUMN` needed.

### Migration file: `011_role_expansion.py`

Upgrade SQL:
```sql
-- 1. Data migration: existing "user" rows → "template_creator"
UPDATE users SET role = 'template_creator' WHERE role = 'user';

-- 2. Update server default (no schema change needed for data type)
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'document_generator';
```

Downgrade SQL:
```sql
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user';
UPDATE users SET role = 'user' WHERE role = 'template_creator';
-- NOTE: document_generator rows have no prior state — downgrade sets them to 'user'
UPDATE users SET role = 'user' WHERE role = 'document_generator';
```

### Deployment order
1. Run migration (existing `user` rows → `template_creator`)
2. Deploy code (new role names active)
3. Verify: no `"user"` rows remain in DB

---

## Tradeoffs

### 1. Role naming convention
- **Selected**: `template_creator` + `document_generator` (English, snake_case)
- Alternative: `creator` + `generator` (shorter, less clear)
- Alternative: `power_user` + `consumer` (semantic, abstract)

**Verdict**: User's choice is the best. Self-documenting names. Consistent with codebase's snake_case for DB values. `template_creator` (16 chars) and `document_generator` (18 chars) fit in the existing `String(20)` column.

### 2. Permission helper architecture
- **Per-role bool helpers** (current pattern): Adding 2 new helpers and extending 9 existing ones means ~11 function bodies each with a 3-way condition. Simple to read, test, and extend. Matches existing codebase style.
- **Capability-based RBAC matrix**: A dict `PERMISSIONS: dict[str, set[str]]` queried by helper functions. Cleaner when adding 5+ roles. More complex now.

**Verdict**: Keep per-role bool helpers. 3 roles is not enough complexity to justify a matrix. The module docstring already says "future role additions can target individual capabilities without collateral changes" — the bool helpers support that perfectly. If the system ever hits 5+ roles, the matrix migration is mechanical.

### 3. Default role for admin-created users
- **Selected**: `document_generator` (least privilege)
- Alternative: `template_creator` (matches what `user` could do)

**Verdict**: `document_generator` is correct. New users should not get upload capabilities by default. An admin can always promote. This is implementable cleanly: just change line 65 of `users.py` from `role="user"` to `role="document_generator"` and update the entity/model default.

---

## Open Questions for Proposal Phase

1. **Can `template_creator` delete templates they own?** Currently `delete_template` is gated by `_check_access(..., require_owner=True)` which allows owner OR admin. A `template_creator` who owns a template CAN delete it today (no new code needed). Is this the intended behavior? Confirm.

2. **Can `template_creator` share templates they own?** Same situation — `share_template` passes `role=current_user.role` to `service.share_template`, which calls `_check_access(..., require_owner=True)`. Owner OR admin can share. `template_creator` is the owner, so yes. Confirm this is intended.

3. **JWT refresh token role propagation bug**: The `/auth/refresh` endpoint at line 147 of `auth.py` does `payload.get("role", "user")`. Since the refresh token payload has no `role` claim (see `jwt_handler.py:32–41`), ANY token refresh will produce an access token with `"user"` role — not the actual user role. This is a **pre-existing bug** that is currently invisible (refresh just preserves `"user"` for all non-admin). After migration, a `template_creator` who refreshes their token will suddenly appear as `"user"` (which won't exist in the DB after migration). Proposal must fix this: the refresh endpoint should look up the user from DB to get the current role.

4. **Spanish UI labels for new roles**: Proposed labels for `EditUserDialog.tsx`:
   - `template_creator` → "Creador de plantillas"
   - `document_generator` → "Generador de documentos"
   Lock these in the proposal.

5. **`validate` and `auto-fix` template endpoints**: Currently gated by `get_current_user` (any authenticated user). Should `document_generator` be able to call these? Recommendation: Yes — harmless read/transform operations. Confirm.

6. **`document_generator` and template generation**: The `document_generator` CAN hit the generate endpoint for templates shared with them — the visibility filter in `_check_access` already enforces this (no share record = 403). No new capability helper needed. Confirm this is correct.

---

## Risks

1. **CRITICAL — JWT refresh drops role**: After migration, the `/auth/refresh` endpoint will produce access tokens with `role="user"` (the fallback in `payload.get("role", "user")`). Since `"user"` won't exist in DB after the migration, this creates inconsistent state for refreshed tokens. Must be fixed before or with this change. Fix: in `/auth/refresh`, query the user from DB and use `user.role`.

2. **Stale tokens after role change**: When an admin changes a user's role, the user's existing access token still carries the old role until it expires (or they log out and back in). This is pre-existing behavior but becomes more impactful with 3 distinct roles. Short access token expiry mitigates this. No architectural change required now, but document.

3. **`document_generator` + upload endpoint**: The `/templates/upload` endpoint currently has NO role check — any authenticated user can upload. After migration, `document_generator` users (who were `user` before) could still upload via direct API calls if the backend gate isn't added. Must add `can_upload_templates` check to the endpoint.

4. **`UploadTemplateDialog` always rendered**: The upload button in `frontend/src/routes/_authenticated/templates/index.tsx` is always rendered regardless of role. After migration, `document_generator` users will see the button and get a 403 from the backend. Must hide it on the frontend.

5. **`upload_new_version` endpoint**: Same as #3 — currently gated only by `_check_access(require_owner=True)`. A `document_generator` user who somehow has a template in their name (shouldn't happen post-migration but possible via direct DB manipulation) could call this. Adding `can_create_template_versions` check closes this hole explicitly.

6. **`tenant.py` middleware default**: Line 44 uses `payload.get("role", "user")`. After migration, if a JWT is issued without a role claim (shouldn't happen in normal flow), it defaults to `"user"` which doesn't exist. Change default to `"document_generator"`.

7. **Existing share recipients**: Any `"user"` who was previously shared a template becomes `"template_creator"` after migration. They'll still see the shared template (share records reference user IDs, not roles). No data issue, but verify share visibility logic doesn't break.

8. **Test suite**: `test_permissions.py` uses `ROLE_EXPECTATIONS` = `[("admin", True), ("user", False), ("unknown_role", False)]`. After migration, `"user"` no longer exists — tests will still pass (it maps to False for all non-admin helpers), but new rows for `"template_creator"` and `"document_generator"` need to be added to accurately reflect the new truth table.

---

## Files I Read

- `backend/src/app/domain/services/permissions.py` — 7 bool helpers + `is_admin_role`, all `role == "admin"`. Single source of truth for RBAC.
- `backend/src/app/domain/services/document_permissions.py` — `DOWNLOAD_FORMAT_PERMISSIONS` dict with `admin`→both, `user`→pdf. Default for unknown = pdf-only.
- `backend/src/app/domain/entities/user.py` — `User` dataclass, `role: str = "user"` default at line 13.
- `backend/src/app/infrastructure/persistence/models/user.py` — `role` is `String(20)` column. SAFE for 18-char `document_generator`.
- `backend/src/app/application/services/signup_service.py` — First user gets `role="admin"` (line 129). Do not touch.
- `backend/src/app/presentation/api/v1/users.py` — `create_user` hard-codes `role="user"` (line 65). Must change.
- `backend/src/app/presentation/schemas/user.py` — `validate_role` whitelists only `"admin"` or `"user"` (line 33). Must add new roles.
- `backend/src/app/infrastructure/persistence/repositories/user_repository.py` — `count_admins_by_tenant` uses `UserModel.role == "admin"` (line 84). Correct, no change.
- `backend/src/app/presentation/api/v1/templates.py` — `upload_template` (POST /upload) and `upload_new_version` (POST /{id}/versions) have NO role check, only authentication. Must add gate.
- `backend/src/app/application/services/template_service.py` — `_check_access` uses `can_view_all_templates` OR ownership/share. Naturally correct for 3 roles.
- `backend/src/app/infrastructure/auth/jwt_handler.py` — Refresh token has NO `role` claim in payload. Critical bug source.
- `backend/src/app/presentation/api/v1/auth.py` — `/refresh` uses `payload.get("role", "user")` — the bug materializes here at line 147.
- `backend/src/app/presentation/middleware/tenant.py` — JWT decode defaults `role` to `"user"` at line 44. Must change default.
- `backend/tests/unit/domain/test_permissions.py` — Truth table tests with 3 cases: admin/user/unknown. Must add template_creator/document_generator rows.
- `backend/tests/unit/domain/test_document_permissions.py` — 6 cases: admin+user × pdf+docx + unknown. Must add new role cases.
- `backend/alembic/versions/` — Last migration is `010_pdf_export.py`. New one: `011_role_expansion.py`.
- `frontend/src/shared/lib/auth.tsx` — `role: string` (untyped). No change needed.
- `frontend/src/routes/_authenticated.tsx` — `isAdmin = user?.role === "admin"` (line 26). Correct for 3 roles.
- `frontend/src/features/documents/components/DownloadButton.tsx` — `isAdmin = user?.role === "admin"` (line 45). Correct for 3 roles.
- `frontend/src/features/documents/components/BulkDownloadControls.tsx` — `isAdmin: boolean` prop, checkbox hidden for non-admin. Correct.
- `frontend/src/features/templates/components/TemplateDetail.tsx` — Upload version / Delete / Share buttons gated by `template.is_owner`. Correct by design.
- `frontend/src/routes/_authenticated/templates/index.tsx` — `<UploadTemplateDialog />` always rendered (line 39). Must hide for `document_generator`.
- `frontend/src/features/users/components/EditUserDialog.tsx` — Role `<Select>` has only `admin`/`user` options (lines 127–130). Must add 2 new options.
- `frontend/src/features/users/components/CreateUserDialog.tsx` — No role field. Correct — backend default will change.

---

## Ready for Proposal
Yes. All surface areas identified, critical bug documented, migration strategy validated against column width. Proposal can lock the capability matrix, the refresh fix strategy, and the Spanish UI labels.
