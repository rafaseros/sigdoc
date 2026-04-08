# Tasks: Template Sharing & Per-User Limits

## Phase 1: Migration + Domain Foundation

- [x] 1.1 Create `backend/alembic/versions/003_template_shares_and_user_limits.py` — `upgrade()` creates `template_shares` table (UUID PK, template_id FK CASCADE, user_id FK CASCADE, tenant_id FK, shared_by FK, shared_at, UNIQUE(template_id,user_id), indexes); adds `users.bulk_generation_limit INTEGER NULL`; `downgrade()` reverses both
- [x] 1.2 Create `backend/src/app/domain/entities/template_share.py` — `TemplateShare` dataclass with fields: id, template_id, user_id, tenant_id, shared_by, shared_at
- [x] 1.3 Modify `backend/src/app/domain/entities/user.py` — add `bulk_generation_limit: int | None = None` field
- [x] 1.4 Modify `backend/src/app/domain/entities/__init__.py` — export `TemplateShare`
- [x] 1.5 Modify `backend/src/app/domain/exceptions.py` — add `TemplateAccessDeniedError(DomainError)` and `TemplateSharingError(DomainError)`
- [x] 1.6 Modify `backend/src/app/domain/ports/template_repository.py` — add 5 abstract methods: `list_accessible(user_id, page, size, search)`, `add_share(template_id, user_id, tenant_id, shared_by)`, `remove_share(template_id, user_id)`, `has_access(template_id, user_id)`, `list_shares(template_id)`

## Phase 2: Infrastructure — ORM + Repository

- [x] 2.1 Create `backend/src/app/infrastructure/persistence/models/template_share.py` — `TemplateShareModel` with `UUIDMixin` + `TenantMixin`, all FK columns, `__tablename__ = "template_shares"`, unique constraint, relationship to `TemplateModel` and `UserModel`
- [x] 2.2 Modify `backend/src/app/infrastructure/persistence/models/__init__.py` — import `TemplateShareModel` so Alembic autogenerates correctly
- [x] 2.3 Modify `backend/src/app/infrastructure/persistence/models/user.py` — add `bulk_generation_limit: Mapped[int | None]` column
- [x] 2.4 Modify `backend/src/app/infrastructure/persistence/repositories/template_repository.py` — implement `list_accessible()` using UNION of owned+shared with `access_type` transient attribute; implement `add_share()` with `INSERT ... ON CONFLICT DO NOTHING`; implement `remove_share()`, `has_access()`, `list_shares()`

## Phase 3: Fake Repository + Service Layer

- [x] 3.1 Modify `backend/tests/fakes/fake_template_repository.py` — implement the 5 new abstract methods using in-memory dicts; `list_accessible` filters by `created_by == user_id OR user_id in shares`; `add_share` is idempotent
- [x] 3.2 Modify `backend/src/app/application/services/template_service.py` — add private `_check_access(template_id, user_id, role, require_owner)` raising `TemplateAccessDeniedError`; update `list_templates` → calls `list_accessible`; update `get_template`, `upload_new_version`, `delete_template` to enforce ownership; add `share_template`, `unshare_template`, `list_template_shares` methods
- [x] 3.3 Modify `backend/src/app/application/services/document_service.py` — add `role` param to `generate_single`, `generate_bulk`, `parse_excel_data`; call `has_access` before processing; add `generate_excel_template` access check
- [x] 3.4 Modify `backend/src/app/application/services/__init__.py` — update `get_document_service` factory to resolve per-user `bulk_generation_limit` (user field if non-null, else global setting) and pass to service

## Phase 4: API Layer

- [x] 4.1 Modify `backend/src/app/presentation/schemas/template.py` — add `access_type: str`, `is_owner: bool` to `TemplateResponse`; add `ShareTemplateRequest(BaseModel)` with `user_id: UUID`; add `TemplateShareResponse`
- [x] 4.2 Modify `backend/src/app/presentation/schemas/user.py` — add `bulk_generation_limit: int | None` to `UpdateUserRequest` and `UserResponse`
- [x] 4.3 Modify `backend/src/app/presentation/schemas/auth.py` — add `effective_bulk_limit: int` to auth `UserResponse`
- [x] 4.4 Modify `backend/src/app/presentation/api/v1/templates.py` — update `GET /templates` to pass `user_id`+`role`; update `GET /{id}`, `POST /{id}/versions`, `DELETE /{id}` with access guards; add `POST /{id}/shares`, `DELETE /{id}/shares/{user_id}`, `GET /{id}/shares` endpoints; catch `TemplateAccessDeniedError` → 403
- [x] 4.5 Modify `backend/src/app/presentation/api/v1/documents.py` — pass `role` to service calls; catch `TemplateAccessDeniedError` → 403
- [x] 4.6 Modify `backend/src/app/presentation/api/v1/auth.py` — resolve `effective_bulk_limit` (user field ?? global default) and include in `/me` response
- [x] 4.7 Modify `backend/src/app/presentation/api/v1/users.py` — accept `bulk_generation_limit` in `PUT /users/{id}` (admin-only guard already in place)

## Phase 5: Tests (TDD — RED → GREEN)

- [x] 5.1 Modify `backend/tests/unit/test_template_service.py` — add tests for `_check_access`: owner allowed, shared-user allowed for read, shared-user denied for version/delete, unrelated user denied, admin bypasses all
- [x] 5.2 Modify `backend/tests/unit/test_template_service.py` — add tests for `share_template`: non-owner gets `TemplateAccessDeniedError`, duplicate share is idempotent, cross-tenant user gets `TemplateSharingError`; and `unshare_template`: non-owner denied, successful unshare removes access
- [x] 5.3 Modify `backend/tests/unit/test_template_service.py` — add tests for `list_templates` using fake: user sees owned+shared with correct `access_type`, peer's private template absent
- [x] 5.4 Modify `backend/tests/unit/test_document_service.py` — add tests for access check in generate: unrelated user raises `TemplateAccessDeniedError`, shared user succeeds; per-user limit overrides global; user with null limit falls back to global
- [x] 5.5 Modify `backend/tests/integration/test_templates_api.py` — add integration tests for all spec scenarios: private-by-default, share/unshare flows, listing with `access_type`, version/delete auth, share endpoint 403s
- [x] 5.6 Add `backend/tests/integration/test_template_shares_api.py` — dedicated tests for `POST/DELETE/GET /templates/{id}/shares` endpoints covering all spec scenarios
- [x] 5.7 Modify `backend/tests/integration/test_documents_api.py` — add tests for template access check before generation (403 for unrelated user, 201 for shared user)
- [x] 5.8 Modify `backend/tests/integration/test_auth_api.py` — add test for `effective_bulk_limit` in `/me` response (null limit uses global, set limit returned directly)

## Phase 6: Frontend

- [x] 6.1 Modify `frontend/src/features/templates/api/queries.ts` — update template list query type to include `access_type` and `is_owner`; add `useTemplateShares(templateId)` hook
- [x] 6.2 Modify `frontend/src/features/templates/api/mutations.ts` — add `useShareTemplate()` and `useUnshareTemplate()` mutations calling `POST/DELETE /templates/{id}/shares`
- [x] 6.3 Create `frontend/src/features/templates/components/ShareTemplateDialog.tsx` — modal with user picker (filtered to same tenant), current shares list with revoke buttons; uses `useShareTemplate`, `useUnshareTemplate`, `useTemplateShares`
- [x] 6.4 Modify `frontend/src/features/templates/components/TemplateDetail.tsx` — show share button only when `is_owner`; hide version/delete actions when not `is_owner`; render access type badge
- [x] 6.5 Modify `frontend/src/features/templates/components/TemplateList.tsx` — add `access_type` badge ("Shared" indicator) per template card
- [x] 6.6 Update bulk generation page component — fetch `/auth/me` and display `effective_bulk_limit` as row cap info

## Phase 7: Verification

- [ ] 7.1 Run `alembic upgrade head` against dev DB — verify `template_shares` table and `users.bulk_generation_limit` exist with correct constraints
- [ ] 7.2 Run `alembic downgrade -1` then `alembic upgrade head` — verify round-trip is clean
- [x] 7.3 Run full backend test suite — all 144 tests pass (96 original + 48 new)
- [ ] 7.4 Manual smoke test: create template as user A, confirm user B cannot see it, share with B, confirm B can list and generate but not version/delete
- [ ] 7.5 Manual smoke test: set per-user limit via admin PATCH, verify limit enforced in bulk generation, verify `/auth/me` reflects effective limit
