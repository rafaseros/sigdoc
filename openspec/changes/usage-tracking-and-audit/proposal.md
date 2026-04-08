# Proposal: usage-tracking-and-audit

## Intent

Add two foundational observability subsystems to SigDoc: **usage tracking** (document generation metrics per user/tenant/month) and **audit logging** (immutable record of significant actions). Usage tracking is the prerequisite for subscription tiers and billing — the schema must support monthly quotas from day one. Audit logging provides compliance and operational visibility for multi-tenant SaaS.

## Problem Statement

Today SigDoc has no visibility into how the platform is being used:
- No way to know how many documents a user/tenant generates per month.
- No way to enforce subscription-based quotas (the next planned change).
- No audit trail — if a template is deleted or shared, there is no record of who did it and when.
- Admins have no dashboard to understand tenant activity or investigate incidents.

Without usage tracking, subscription tiers cannot be implemented. Without audit logging, SigDoc cannot meet basic SaaS compliance expectations.

## Scope

### In Scope

1. **Usage Tracking**
   - `usage_events` table: records every document generation event (single + bulk)
   - Fields: `id`, `user_id`, `tenant_id`, `template_id`, `generation_type` (single/bulk), `document_count`, `created_at`
   - `UsageRepository` port + SQLAlchemy adapter with aggregation queries
   - `UsageService` in application layer — called by `DocumentService` after successful generation
   - Aggregation methods: docs this month per user, docs this month per tenant, docs per template
   - API: `GET /api/v1/usage` (current user's monthly usage), `GET /api/v1/usage/tenant` (admin: all users in tenant)
   - Frontend: Usage widget on dashboard (current month docs generated, quota bar if limit exists)

2. **Audit Logging**
   - `audit_logs` table: append-only, immutable log of significant actions
   - Fields: `id`, `actor_id`, `tenant_id`, `action` (enum string), `resource_type`, `resource_id`, `details` (JSONB), `ip_address`, `created_at`
   - Actions tracked: `template.upload`, `template.delete`, `template.version`, `template.share`, `template.unshare`, `document.generate`, `document.generate_bulk`, `document.delete`, `user.create`, `user.update`, `user.delete`, `auth.login`, `auth.login_failed`
   - `AuditRepository` port + SQLAlchemy adapter (write-only + paginated read)
   - `AuditService` in application layer — fire-and-forget pattern (must not block request path)
   - API: `GET /api/v1/audit-log` (admin only, paginated, filterable by action/user/date range)
   - Frontend: Audit log page (admin only) with filters and pagination

3. **Alembic migration** `004_usage_tracking_and_audit_logging`

4. **Tests**: Unit tests for services, integration tests for API endpoints, fake repositories for both

### Out of Scope

- Subscription tier enforcement (next change — `subscription-tiers`)
- Rate limiting per tier (separate change — `rate-limits-per-tier`)
- Email/webhook notifications on audit events
- Audit log export (CSV/PDF) — future enhancement
- Real-time usage alerts
- Background job for usage aggregation (sync aggregation is sufficient at current scale)

## Approach

### Architecture Decision: Service-Layer Event Emission (not middleware)

**Why not middleware/decorator?**
- Middleware cannot know the business outcome (e.g., how many docs were generated in a bulk operation, whether it succeeded or failed).
- The document count for bulk generation is only known after processing all rows.
- Audit details (resource_id, action specifics) are only available inside the service method.

**Chosen approach**: Each service method that produces a trackable event calls `UsageService.record()` and/or `AuditService.log()` after the business operation succeeds. This keeps the tracking logic explicit, testable, and coupled to actual outcomes rather than HTTP requests.

**Fire-and-forget for audit**: `AuditService.log()` will use `asyncio.create_task()` to write asynchronously. If the audit write fails, it logs a warning but does NOT fail the parent request. Usage tracking writes synchronously (within the same transaction) because usage data feeds quota enforcement.

### Schema Design

#### `usage_events` table

```
usage_events
├── id              UUID PK
├── tenant_id       UUID FK(tenants.id) NOT NULL — TenantMixin
├── user_id         UUID FK(users.id) NOT NULL
├── template_id     UUID FK(templates.id) NOT NULL
├── generation_type VARCHAR(10) NOT NULL — "single" | "bulk"
├── document_count  INTEGER NOT NULL — 1 for single, N for bulk
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
│
├── INDEX ix_usage_tenant_month (tenant_id, created_at)  — for tenant aggregation
├── INDEX ix_usage_user_month (user_id, created_at)      — for user aggregation
└── INDEX ix_usage_template (template_id)                 — for per-template stats
```

**Design for subscription tiers**: The `document_count` field allows a simple `SUM(document_count) WHERE user_id = X AND created_at >= month_start` to check quota. No separate aggregation table needed at current scale. When scale demands it, a materialized view or periodic rollup can be added without schema changes.

#### `audit_logs` table

```
audit_logs
├── id              UUID PK
├── tenant_id       UUID FK(tenants.id) NOT NULL — TenantMixin
├── actor_id        UUID FK(users.id) NULL — NULL for system actions
├── action          VARCHAR(50) NOT NULL — e.g. "template.upload"
├── resource_type   VARCHAR(30) NOT NULL — e.g. "template", "document", "user"
├── resource_id     UUID NULL — NULL when resource was created (ID not yet known) or for login events
├── details         JSONB NULL — action-specific metadata
├── ip_address      VARCHAR(45) NULL — supports IPv6
├── created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
│
├── INDEX ix_audit_tenant_created (tenant_id, created_at DESC)  — main query path
├── INDEX ix_audit_action (action)                                — filter by action type
└── INDEX ix_audit_actor (actor_id)                               — filter by user
```

**Immutability**: The audit_logs table has NO `updated_at` column. The `AuditRepository` exposes only `create()` and `list_paginated()` — no update or delete methods. The Alembic migration should add a comment: "append-only table — do not add UPDATE/DELETE operations."

### Clean Architecture Layers

```
domain/
├── entities/usage_event.py          — UsageEvent dataclass
├── entities/audit_log.py            — AuditLog dataclass
├── ports/usage_repository.py        — UsageRepository ABC
├── ports/audit_repository.py        — AuditRepository ABC

application/
├── services/usage_service.py        — UsageService (record + aggregate)
├── services/audit_service.py        — AuditService (log + list)

infrastructure/
├── persistence/models/usage_event.py      — UsageEventModel (SQLAlchemy)
├── persistence/models/audit_log.py        — AuditLogModel (SQLAlchemy)
├── persistence/repositories/usage_repository.py   — SQLAlchemyUsageRepository
├── persistence/repositories/audit_repository.py   — SQLAlchemyAuditRepository

presentation/
├── api/v1/usage.py                  — Usage endpoints
├── api/v1/audit.py                  — Audit log endpoints
├── schemas/usage.py                 — Pydantic schemas
├── schemas/audit.py                 — Pydantic schemas
```

### Integration Points

1. **DocumentService.generate_single()** → after success:
   - `usage_service.record(user_id, tenant_id, template_id, "single", document_count=1)`
   - `audit_service.log(actor_id, tenant_id, "document.generate", "document", doc_id, details={...})`

2. **DocumentService.generate_bulk()** → after success:
   - `usage_service.record(user_id, tenant_id, template_id, "bulk", document_count=len(success))`
   - `audit_service.log(actor_id, tenant_id, "document.generate_bulk", "document", batch_id, details={count, errors})`

3. **TemplateService.upload_template()** → `audit_service.log(..., "template.upload", ...)`
4. **TemplateService.upload_new_version()** → `audit_service.log(..., "template.version", ...)`
5. **TemplateService.delete_template()** → `audit_service.log(..., "template.delete", ...)`
6. **TemplateService.share_template()** → `audit_service.log(..., "template.share", ...)`
7. **TemplateService.unshare_template()** → `audit_service.log(..., "template.unshare", ...)`
8. **DocumentService.delete_document()** → `audit_service.log(..., "document.delete", ...)`
9. **Auth login endpoint** → `audit_service.log(..., "auth.login", ...)` / `audit_service.log(..., "auth.login_failed", ...)`
10. **User CRUD endpoints** → `audit_service.log(..., "user.create"/"user.update"/"user.delete", ...)`

### IP Address Capture

The `Request` object is available in FastAPI endpoints. The IP address will be extracted in the presentation layer and passed to services as a parameter (services should not depend on HTTP concepts). Pattern: `ip_address = request.client.host if request.client else None`.

### Service Injection

Both `UsageService` and `AuditService` will be injected into `DocumentService` and `TemplateService` via the existing DI pattern in `application/services/__init__.py`. The services accept repository ports in their constructors, keeping them testable with fakes.

For audit logging in auth endpoints (which don't use a service layer), the `AuditService` will be injected directly via FastAPI `Depends()`.

### Frontend

1. **Usage Widget** (dashboard/index page):
   - Card showing: "Documents generated this month: X" with optional quota bar
   - Uses `GET /api/v1/usage`
   - Placed in `frontend/src/features/usage/` following existing feature structure

2. **Audit Log Page** (admin only):
   - New route: `/_authenticated/audit-log/index.tsx`
   - Table with columns: Timestamp, User, Action, Resource, Details
   - Filters: action type dropdown, user search, date range picker
   - Pagination matching existing pattern (page/size)
   - Feature module: `frontend/src/features/audit/`
   - Only visible in nav when `role === "admin"`

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Audit logging slows down request path | Medium | High | Fire-and-forget via `asyncio.create_task()` — audit write failures logged but don't propagate |
| Usage table grows large over time | Low (near-term) | Medium | Indexed on (tenant_id, created_at) for efficient monthly queries. Future: add rollup/archival job |
| Audit log table grows unbounded | Medium | Medium | Paginated reads only. Future: add retention policy / archival to cold storage |
| Breaking existing service constructors | Low | High | Add usage_service and audit_service as optional parameters with `None` default — backward compatible |
| IP address extraction edge cases (proxies) | Medium | Low | Use `request.client.host` for now; add `X-Forwarded-For` header parsing when behind nginx (document as known limitation) |

## Dependencies

- **Requires**: Nothing — this change is self-contained
- **Enables**: `subscription-tiers` (needs usage aggregation to enforce quotas), `rate-limits-per-tier` (needs usage data)
- **Migration**: `004` — depends on existing schema from migrations 001-003

## Success Criteria

1. Every document generation (single + bulk) creates a usage_event record
2. `GET /api/v1/usage` returns current user's monthly document count
3. `GET /api/v1/usage/tenant` returns per-user breakdown for admin
4. Every significant action creates an audit_log entry
5. `GET /api/v1/audit-log` returns paginated, filterable audit entries (admin only)
6. Audit logging does not measurably increase endpoint latency
7. Frontend shows usage widget on dashboard
8. Frontend shows audit log page for admins
9. All new code covered by unit + integration tests
10. All existing 144 tests continue to pass
