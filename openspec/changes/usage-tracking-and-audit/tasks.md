# Tasks: usage-tracking-and-audit

> TDD: RED (failing test) → GREEN (implementation) → tasks are paired accordingly.
> Existing 144 tests must pass at every phase boundary.

---

## Phase 1: Migration + Domain

- [x] 1.1 Create `backend/alembic/versions/004_usage_tracking_and_audit_logging.py` — `usage_events` + `audit_logs` tables with all indexes; set `down_revision = "003_..."`
- [x] 1.2 Create `backend/src/app/domain/entities/usage_event.py` — `@dataclass UsageEvent` (id, user_id, tenant_id, template_id, generation_type, document_count, created_at)
- [x] 1.3 Create `backend/src/app/domain/entities/audit_log.py` — `@dataclass AuditLog` + `AuditAction` string constants (13 values from spec)
- [x] 1.4 Update `backend/src/app/domain/entities/__init__.py` — export `UsageEvent`, `AuditLog`, `AuditAction`
- [x] 1.5 Create `backend/src/app/domain/ports/usage_repository.py` — `UsageRepository(ABC)` with 5 abstract methods (create, get_user_month_total, get_tenant_month_total, get_tenant_user_breakdown, get_template_month_total)
- [x] 1.6 Create `backend/src/app/domain/ports/audit_repository.py` — `AuditRepository(ABC)` with 2 abstract methods (create, list_paginated); NO update/delete
- [x] 1.7 Update `backend/src/app/domain/ports/__init__.py` — export both new ports

---

## Phase 2: Infrastructure (ORM + Repositories)

- [x] 2.1 Create `backend/src/app/infrastructure/persistence/models/usage_event.py` — `UsageEventModel(Base, UUIDMixin)` mapped to `usage_events`; NO `updated_at`; FK to tenants, users, templates
- [x] 2.2 Create `backend/src/app/infrastructure/persistence/models/audit_log.py` — `AuditLogModel(Base, UUIDMixin)` mapped to `audit_logs`; actor_id NULLABLE; details JSONB; NO `updated_at`
- [x] 2.3 Update `backend/src/app/infrastructure/persistence/models/__init__.py` — import both models so Alembic detects them
- [x] 2.4 Create `backend/src/app/infrastructure/persistence/repositories/usage_repository.py` — `SQLAlchemyUsageRepository(UsageRepository)` with `SUM(document_count)` aggregation queries; month_start computed from `(year, month)` params
- [x] 2.5 Create `backend/src/app/infrastructure/persistence/repositories/audit_repository.py` — `SQLAlchemyAuditRepository(AuditRepository)` with paginated query (order by created_at DESC); dynamic filter building for action/actor_id/date_from/date_to
- [x] 2.6 Update `backend/src/app/infrastructure/persistence/repositories/__init__.py` — export both new repos

---

## Phase 3: Fakes (test doubles — write BEFORE services)

- [x] 3.1 Create `backend/tests/fakes/fake_usage_repository.py` — `FakeUsageRepository(UsageRepository)` backed by `list[UsageEvent]`; aggregation via list comprehension using `month_start` date
- [x] 3.2 Create `backend/tests/fakes/fake_audit_repository.py` — `FakeAuditRepository(AuditRepository)` backed by `list[AuditLog]`; `list_paginated` slices + filters in Python
- [x] 3.3 Update `backend/tests/fakes/__init__.py` — export `FakeUsageRepository`, `FakeAuditRepository`

---

## Phase 4: Services — TDD RED then GREEN

- [x] 4.1 **RED** — Create `backend/tests/unit/test_usage_service.py`: write failing tests for `UsageService.record()` (appends event), `get_current_month_usage()` (sum), `get_tenant_usage()` (breakdown dict); use `FakeUsageRepository`
- [x] 4.2 **GREEN** — Create `backend/src/app/application/services/usage_service.py`: `UsageService(usage_repo)` with sync methods; `record()` wraps in try/except — warns but never raises
- [x] 4.3 **RED** — Create `backend/tests/unit/test_audit_service.py`: write failing tests for `AuditService.log()` (creates entry), `list_audit_logs()` (delegates to repo); use `FakeAuditRepository`; test that log() failure is swallowed; test async task is spawned
- [x] 4.4 **GREEN** — Create `backend/src/app/application/services/audit_service.py`: `AuditService(session_factory)` — `log()` spawns `asyncio.create_task(_write(entry))`; `_write()` creates own session, commits independently; `list_audit_logs()` uses fresh session
- [x] 4.5 Update `backend/src/app/application/services/__init__.py` — add `get_usage_service(session)` and `get_audit_service()` factory functions; update `get_document_service` and `get_template_service` to inject both (optional params, None default)

---

## Phase 5: Service Integration — TDD RED then GREEN

- [x] 5.1 **RED** — Extend `backend/tests/unit/test_document_service.py`: add tests verifying `generate_single` calls `usage_service.record(type="single", count=1)` and `audit_service.log(DOCUMENT_GENERATE)` after `doc_repo.create()`; test that None usage_service skips without error
- [x] 5.2 **GREEN** — Update `backend/src/app/application/services/document_service.py`: add optional `usage_service: UsageService | None = None` and `audit_service: AuditService | None = None` and `ip_address: str | None = None` params to `__init__`; call both after `doc_repo.create()` in `generate_single()`
- [x] 5.3 **RED** — Extend `test_document_service.py`: add tests for `generate_bulk` calling `usage_service.record(type="bulk", count=len(success))` and `audit_service.log(DOCUMENT_GENERATE_BULK)`; add test for `delete_document` calling `audit_service.log(DOCUMENT_DELETE)`
- [x] 5.4 **GREEN** — Update `document_service.py`: wire `generate_bulk()` and `delete_document()` audit/usage calls
- [x] 5.5 **RED** — Extend `backend/tests/unit/test_template_service.py` (create if not exists): tests for `upload_template`, `upload_new_version`, `delete_template`, `share_template`, `unshare_template` each calling `audit_service.log(correct_action)`; test None audit_service skips
- [x] 5.6 **GREEN** — Update `backend/src/app/application/services/template_service.py`: add optional `audit_service: AuditService | None = None` and `ip_address: str | None = None`; wire audit calls in each method

---

## Phase 6: Routers — Direct Audit Calls

- [x] 6.1 Update `backend/src/app/presentation/api/v1/auth.py`: after successful login call `audit_service.log(AUTH_LOGIN, ip=request.client.host)`; after change-password call `audit_service.log(AUTH_CHANGE_PASSWORD)`
- [x] 6.2 Update `backend/src/app/presentation/api/v1/users.py`: after create → `audit_service.log(USER_CREATE)`; after update → `USER_UPDATE`; after deactivate → `USER_DEACTIVATE`; inject `audit_service = Depends(get_audit_service)`

---

## Phase 7: API Endpoints + Schemas

- [x] 7.1 Create `backend/src/app/presentation/schemas/usage.py` — `UserUsageResponse`, `TenantUsageResponse`, `TemplateUsageStat`, `UserUsageStat` Pydantic models
- [x] 7.2 Create `backend/src/app/presentation/schemas/audit.py` — `AuditLogResponse`, `AuditLogListResponse` Pydantic models; `AuditActionEnum` (FastAPI query param type)
- [x] 7.3 Create `backend/src/app/presentation/api/v1/usage.py` — `GET /usage` (current user, own stats; query: year, month) + `GET /usage/tenant` (admin only, 403 for non-admin)
- [x] 7.4 Create `backend/src/app/presentation/api/v1/audit.py` — `GET /audit-log` (admin only, 403 non-admin; query: page, size, action, actor_id, date_from, date_to); ordered by `created_at DESC`
- [x] 7.5 Update `backend/src/app/main.py` — register `usage_router` and `audit_router` under `/api/v1`

---

## Phase 8: Integration Tests — TDD RED then GREEN

- [x] 8.1 **RED** — Create `backend/tests/integration/test_usage_api.py`: test `GET /api/v1/usage` returns 200 with correct shape (no auth → 401; non-admin → own stats; wrong year/month → 422)
- [x] 8.2 **GREEN** — Wire `FakeUsageRepository` into integration `conftest.py` override for `get_usage_service`; confirm tests pass
- [x] 8.3 **RED** — Add `GET /api/v1/usage/tenant` tests: admin → 200 with by_user list; non-admin → 403
- [x] 8.4 **GREEN** — Adjust role logic in usage router; tests pass
- [x] 8.5 **RED** — Create `backend/tests/integration/test_audit_api.py`: test `GET /api/v1/audit-log` admin → 200 paginated; non-admin → 403; filter params → correct subset; page/size bounds
- [x] 8.6 **GREEN** — Wire `FakeAuditRepository` into integration conftest; confirm tests pass
- [x] 8.7 Verify full suite: `pytest backend/tests/ -x -q` → all 144 + new tests pass (188 total)

---

## Phase 9: Frontend

- [ ] 9.1 Create `frontend/src/features/usage/api/keys.ts` — query key factory `usageKeys`
- [ ] 9.2 Create `frontend/src/features/usage/api/queries.ts` — `useUserUsage(year, month)` and `useTenantUsage(year, month)` React Query hooks
- [ ] 9.3 Create `frontend/src/features/usage/api/index.ts` — re-export
- [ ] 9.4 Create `frontend/src/features/usage/components/UsageWidget.tsx` — card showing "Documents generated this month: X"; skeleton while loading; uses `useUserUsage`
- [ ] 9.5 Update `frontend/src/routes/_authenticated/index.tsx` (dashboard) — import and render `<UsageWidget />`
- [ ] 9.6 Create `frontend/src/features/audit/api/keys.ts` + `queries.ts` + `index.ts` — `useAuditLog({ page, size, action, actor_id, date_from, date_to })` React Query hook
- [ ] 9.7 Create `frontend/src/features/audit/components/AuditFilters.tsx` — filter bar (action select, date range inputs, actor search)
- [ ] 9.8 Create `frontend/src/features/audit/components/AuditLogTable.tsx` — paginated table using `<Table>` UI component; columns: timestamp, actor, action, resource, details; admin-only
- [ ] 9.9 Create `frontend/src/routes/_authenticated/audit/index.tsx` — audit log page; renders `<AuditFilters>` + `<AuditLogTable>`; redirects non-admin to dashboard
- [ ] 9.10 Update `frontend/src/routes/__root.tsx` — add Audit link to nav (admin only)
- [ ] 9.11 Regenerate `frontend/src/routeTree.gen.ts` via `npx tsr generate`

---

## Phase 10: Verification

- [ ] 10.1 Run `pytest backend/tests/ -q` — confirm all (144 + new) tests pass, no regressions
- [ ] 10.2 Check `AuditService.log()` failure path: kill DB in test, verify parent endpoint still returns 2xx
- [ ] 10.3 Confirm `usage_service=None` in DocumentService doesn't break any existing integration tests
- [ ] 10.4 Manual smoke: run `alembic upgrade head`, generate a doc, query `GET /api/v1/usage`, query `GET /api/v1/audit-log`
- [ ] 10.5 Verify `audit_logs.tenant_id NOT NULL` constraint holds — no orphaned audit entries
