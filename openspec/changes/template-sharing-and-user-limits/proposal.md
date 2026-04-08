# Proposal: Template Sharing & Per-User Limits

## Intent

Templates are tenant-wide today — any user can see, version, and delete any template. For SaaS, templates must be **private by default** with explicit sharing, and bulk generation limits must be **per-user** (not global) to support subscription tiers.

## Scope

### In Scope
- Private-by-default templates with owner-controlled sharing
- Shared users can USE (generate) but NOT version/delete
- Per-user `bulk_generation_limit` field (default from Settings, admin-overridable)
- Alembic migration for new table + column
- Updated authorization checks in service + API layers
- Frontend adjustments for share UI and visibility filtering

### Out of Scope
- Subscription tier model / billing integration
- Team/group sharing (only user-to-user for now)
- Template marketplace or cross-tenant sharing
- Role-based limit profiles (future tier system)

## Capabilities

### New Capabilities
- `template-sharing`: Private-by-default templates, share with specific users, permission model (owner vs shared-user)

### Modified Capabilities
- `template-management`: List/get/version/delete now enforce ownership and sharing permissions
- `document-generation`: Bulk limit read from user model instead of global Settings

## Approach

**Sharing**: New `template_shares` join table (`template_id`, `user_id`, `tenant_id`, timestamps). Repository gets `list_accessible(user_id)` that returns owned + shared templates. Service layer enforces: only owner can version/delete; shared users can only generate.

**Per-user limits**: Add `bulk_generation_limit` nullable int column to `users` table. `DocumentService` receives the user's limit (fallback to Settings default). No new table needed — the column lives on the user, ready for a future `subscription_tier` FK to override it.

**Admin bypass**: Admins see all tenant templates (existing behavior preserved). Admins can set per-user limits.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/app/infrastructure/persistence/models/user.py` | Modified | Add `bulk_generation_limit` column |
| `backend/src/app/infrastructure/persistence/models/` | New | `template_share.py` — join table model |
| `backend/src/app/domain/entities/user.py` | Modified | Add `bulk_generation_limit` field |
| `backend/src/app/domain/entities/` | New | `template_share.py` — domain entity |
| `backend/src/app/domain/ports/template_repository.py` | Modified | Add `list_accessible()`, sharing CRUD |
| `backend/src/app/application/services/template_service.py` | Modified | Ownership checks, share/unshare methods |
| `backend/src/app/application/services/document_service.py` | Modified | Accept user-specific bulk limit |
| `backend/src/app/presentation/api/v1/templates.py` | Modified | Auth guards, share endpoints, filtered listing |
| `backend/src/app/presentation/api/v1/documents.py` | Modified | Pass user's bulk limit to service |
| `backend/alembic/versions/` | New | Migration for `template_shares` table + `users.bulk_generation_limit` |
| `frontend/src/` | Modified | Share UI components, visibility filtering |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Breaking existing template listing for current users | Med | Migration sets all existing templates visible to all tenant users via backfill shares OR admin-sees-all logic |
| N+1 queries on share lookups | Med | Use `selectin` loading; index on `(template_id, user_id)` |
| Orphaned shares after user deactivation | Low | Cascade delete on user FK; deactivated users' shares become no-ops |
| Frontend complexity for share management | Low | Start with simple user-picker modal; no complex permission UI |

## Rollback Plan

1. Revert Alembic migration (downgrade drops `template_shares` table + `users.bulk_generation_limit` column)
2. Revert service/API code — templates return to tenant-wide visibility
3. Bulk limit falls back to global `Settings.bulk_generation_limit` (already the default)

## Dependencies

- Hardening & testing change should be complete (test infrastructure needed for TDD)
- Alembic must be operational for migration

## Success Criteria

- [ ] Templates are private by default — new template only visible to creator
- [ ] Owner can share template with specific tenant users
- [ ] Shared users can generate documents but cannot version or delete
- [ ] Admin sees all tenant templates (existing behavior preserved)
- [ ] Per-user bulk limit overrides global default
- [ ] Admin can set a user's bulk limit
- [ ] Existing data migrated without breaking access (backfill strategy)
- [ ] All new behavior covered by unit + integration tests
