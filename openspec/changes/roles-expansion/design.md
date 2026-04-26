# Design: roles-expansion

## Technical Approach

Expand the `permissions.py` / `require_capability` infrastructure mechanically: one new helper, one pre-bound dependency, two endpoint gates, one Alembic data migration, schema validator broadening. Fix the pre-existing `/auth/refresh` bug by re-fetching the user from DB (single source of truth). Frontend mirrors backend with a tiny `permissions.ts` and a `ROLE_LABELS` map; UI gates upload behind a role check and adds a role badge in the authenticated header.

## Component Map

```
Frontend                                         Backend
────────                                         ───────
shared/lib/permissions.ts (NEW) ─────────────► (mirrors) domain/services/permissions.py [MOD]
shared/lib/role-labels.ts (NEW)                          │
                                                         ▼
routes/_authenticated/templates/index.tsx [MOD]   presentation/api/dependencies.py [MOD]
features/users/components/EditUserDialog.tsx [MOD]       │
routes/_authenticated.tsx [MOD]                          ▼
                                          presentation/api/v1/templates.py [MOD]
                                          presentation/api/v1/users.py [MOD]
                                          presentation/api/v1/auth.py [MOD]  ─── repo.get_by_id ──┐
                                                                                                  ▼
                                          domain/entities/user.py [MOD]      infrastructure/persistence/repositories/user_repository.py
                                          infrastructure/persistence/models/user.py [MOD]
                                          presentation/schemas/user.py [MOD]
                                          alembic/versions/011_role_expansion.py [NEW]
```

## Architecture Decisions

### ADR-ROLE-01: `/auth/refresh` re-fetches role from DB (REQ-ROLE-09, REQ-ROLE-10)
**Choice**: Replace `payload.get("role", "user")` with a DB lookup using `sub` claim. Inject `AsyncSession` via `Depends(get_session)`. If `repo.get_by_id(UUID(sub))` returns `None` or `is_active=False`, raise 401. Otherwise issue access token with `user.role`.
**Sequence**: decode → validate type=`refresh` → fetch user → 401 if missing/inactive → mint access token from `user.role` → return tokens.
**Rationale**: Single source of truth. Role revocations propagate on next refresh (~15 min). Cost is one PK lookup — negligible. Refresh tokens issued before the change have no `role` claim; they keep working because the claim is now ignored. Backward compatible.

### ADR-ROLE-02: Migration `011_role_expansion.py` shape
`revision="011"`, `down_revision="010"` (next free slot, verified `010_pdf_export.py` is latest). Body:
```python
def upgrade() -> None:
    op.execute("UPDATE users SET role = 'template_creator' WHERE role = 'user'")
    op.alter_column('users', 'role', existing_type=sa.String(20),
                    server_default='document_generator')

def downgrade() -> None:  # LOSSY — collapses both new roles into 'user'
    op.alter_column('users', 'role', existing_type=sa.String(20),
                    server_default='user')
    op.execute("UPDATE users SET role = 'user' "
               "WHERE role IN ('template_creator', 'document_generator')")
```
**Rationale**: Order matters in `upgrade()` — UPDATE runs while rows are still `'user'`, before the default flips. Idempotent (WHERE matches nothing on re-run). Column type unchanged (`String(20)` already fits). Downgrade lossiness documented in docstring.

### ADR-ROLE-03: Entity & ORM defaults (REQ-ROLE-04, REQ-ROLE-05)
- `domain/entities/user.py:13` → `role: str = "document_generator"`.
- `infrastructure/persistence/models/user.py:19` → `default="document_generator", server_default="document_generator"`.
- `presentation/middleware/tenant.py:44` → `role=payload.get("role", "document_generator")` (safe-default deny vs. legacy `"user"`).

### ADR-ROLE-04: Schema validator broadens to 3-role set (REQ-ROLE-06)
`UpdateUserRequest.validate_role` (`presentation/schemas/user.py:33`): replace `("admin", "user")` with `("admin", "template_creator", "document_generator")`; error message names all three. `CreateUserRequest` is NOT modified — no `role` field exists today and none is added (REQ-ROLE-08 default applied at endpoint level).

### ADR-ROLE-05: Default applied in `POST /users` (REQ-ROLE-08)
`presentation/api/v1/users.py:65` — change literal `role="user"` to `role="document_generator"`. Explicit assignment (not Pydantic default) keeps the policy visible in the endpoint. Signup first-user `role="admin"` (`signup_service.py`) is unchanged — it is also an explicit assignment, not a default.

### ADR-TMP-01: `can_manage_own_templates` helper (REQ-TMP-01)
Add to `domain/services/permissions.py` next to existing helpers:
```python
def can_manage_own_templates(role: str) -> bool:
    return role in {"admin", "template_creator"}
```
Add to `__all__`. Unknown role → False (matches existing safe-default pattern).

### ADR-TMP-02: `require_template_manager` dependency (REQ-TMP-02)
In `presentation/api/dependencies.py`, mirroring existing pre-bound deps:
```python
require_template_manager = require_capability(can_manage_own_templates)
```
Spanish 403 detail reuses the module-level `_FORBIDDEN_DETAIL` (already Spanish). No new constant needed; the message "Solo administradores..." is acceptable since it covers the same denial concept (alternative: parameterize `_FORBIDDEN_DETAIL` per dep — out of scope, defer to follow-up).

### ADR-TMP-03: Wiring the gates (REQ-TMP-03, REQ-TMP-04)
- `POST /templates/upload` (`templates.py:94`): add `_: CurrentUser = Depends(require_template_manager)` (or replace `current_user = Depends(get_current_user)`).
- `POST /templates/{template_id}/versions` (`templates.py:156`): same pattern. The handler still needs `current_user` for `tenant_id`/`user_id`/`role`, so we replace `get_current_user` with `require_template_manager` (returns the same `CurrentUser`).
- DELETE/UPDATE template endpoints: NOT gated with `require_template_manager`. The existing ownership check inside the service raises `TemplateAccessDeniedError` for non-owners, and `document_generator` owns nothing → already excluded. Layering the role gate is redundant and risks coupling.

### ADR-FE-01: Frontend permissions module
New file `frontend/src/shared/lib/permissions.ts`:
```ts
export type Role = "admin" | "template_creator" | "document_generator";
export const canUploadTemplates = (r: string | undefined): boolean =>
  r === "admin" || r === "template_creator";
export const canManageUsers = (r: string | undefined): boolean => r === "admin";
export const canViewAudit = (r: string | undefined): boolean => r === "admin";
```
**Rationale**: Mirror backend names; backend remains authoritative — FE drift is a UX bug, never a security hole.

### ADR-FE-02: Role labels module (REQ-TMP-08)
New file `frontend/src/shared/lib/role-labels.ts`:
```ts
import type { Role } from "./permissions";
export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  template_creator: "Creador de plantillas",
  document_generator: "Generador de documentos",
};
export const roleLabel = (r: string | undefined): string =>
  ROLE_LABELS[r as Role] ?? "Usuario";
```
Fallback `"Usuario"` for unknown roles (e.g., stale tokens carrying `"user"` between deploy steps).

### ADR-FE-03: Conditional render + role badge (REQ-TMP-07, REQ-TMP-09, REQ-TMP-10)
- `templates/index.tsx:39` → wrap `<UploadTemplateDialog />` with `{canUploadTemplates(user?.role) && <UploadTemplateDialog />}`. Element absent in DOM (per SCEN-TMP-09).
- `_authenticated.tsx:73` → small shadcn `<Badge variant="secondary">{roleLabel(user?.role)}</Badge>` next to the email span.
- `EditUserDialog.tsx:128-129` → expand SelectItems to three: `admin`/`template_creator`/`document_generator` with values mapped through `ROLE_LABELS` for display. Default-state fallback `setRole(v ?? "document_generator")`.

### ADR-FE-04: Route guards — DEFER
TanStack Router `beforeLoad` guards on `/users`, `/audit`, `/usage` would polish UX (currently a non-admin who types the URL hits the API and gets 403 → blank page). Backend protection is the real defense and is in scope. Pattern is the same as the existing token check in `_authenticated.tsx`. Decision: **defer to a follow-up change** — out of scope here, recorded as open question for tasks/apply.

### ADR-TEST-01: Test strategy (REQ trace via D-10)
| Layer | What | Where |
|---|---|---|
| Unit | `can_manage_own_templates` truth table (3 roles + unknown) | `tests/unit/domain/test_permissions.py` (extend) |
| Unit | `validate_role` accepts 3 names, rejects others | `tests/unit/presentation/test_role_validation.py` (NEW) |
| Integration | Migration upgrade + downgrade round-trip | `tests/integration/test_role_migration.py` (NEW) |
| Integration | `/auth/refresh` reads role from DB; deleted user → 401 | `tests/integration/test_auth_refresh_role.py` (NEW) |
| Integration | Per-role × per-endpoint upload + version (200/403) | `tests/integration/test_template_endpoint_gates.py` (NEW) |
| Integration | `POST /users` without role defaults to `document_generator` | extend `tests/integration/test_users_api.py` |
| Frontend | Manual + typecheck + lint (no test runner) | — |

## Data Flow

```
/auth/refresh:
client ──► refresh_token ──► decode + validate type ──► repo.get_by_id(sub)
                                                              │
                              ┌── None / inactive ────────────┘
                              ▼                               (live row)
                            HTTP 401                              │
                                                                   ▼
                                           create_access_token(role=user.role)

POST /templates/upload:
client ──► require_template_manager ──► can_manage_own_templates(role)
                                                  │
                                                  ├── False ──► HTTP 403 "Solo..."
                                                  └── True ───► upload_template(...)
```

## File Changes (delta from proposal Module Map)

Confirmed accurate. Verified line numbers: `users.py:65`, `templates.py:94/156`, `auth.py:147`, `tenant.py:44`, `entities/user.py:13`, `models/user.py:19`, `schemas/user.py:33`. No additional files discovered.

## Migration / Rollout

`alembic upgrade head` → `011_role_expansion.py` runs UPDATE then ALTER DEFAULT (single transaction). Order: migration → backend deploy → frontend deploy. After migration, no `'user'` rows remain; legacy access tokens still valid until expiry (~15 min) carrying `"user"` claim — `permissions.py` helpers all return False for `"user"` (safe-degrade to least privilege). On next refresh, ADR-ROLE-01 picks up the DB role.

## Open Questions

- [ ] Per-dep Spanish 403 message — `_FORBIDDEN_DETAIL` is shared and admin-flavored; cosmetic only, defer.
- [ ] FE route guards on admin pages (ADR-FE-04) — UX polish, defer to follow-up change.

## Risks

- **Migration ordering**: UPDATE must precede default flip; verified order in `upgrade()` body. Apply must NOT swap.
- **In-flight access tokens**: pre-existing limitation, now more visible. Mitigated by short TTL + ADR-ROLE-01.
- **FE/BE drift**: `permissions.ts` mirrors backend by hand. Mitigation: helpers are single-line; comment in `permissions.ts` points to `domain/services/permissions.py`.
- **Shared `_FORBIDDEN_DETAIL`**: 403 message says "Solo administradores..." for template-manager denials too. Cosmetic; non-blocking.
