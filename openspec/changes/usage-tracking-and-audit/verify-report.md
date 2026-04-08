# Verify Report: usage-tracking-and-audit

**Status**: WARNING
**Run date**: 2026-04-07
**Test result**: 188 passed / 0 failed / 1 warning (passlib deprecation — unrelated)
**Critical count**: 0
**Warning count**: 3
**Pass count**: 28

---

## Test Suite

```
pytest tests/ -v --tb=short
======================== 188 passed, 1 warning in 7.00s ========================
```

All 188 tests pass. Prior suite (144 tests) has zero regressions. New tests: 44.

---

## PASS Items

### Phase 1 — Migration + Domain

| Item | File | Result |
|------|------|--------|
| Migration 004 | `alembic/versions/004_usage_tracking_and_audit_logging.py` | PASS |
| usage_events table + 3 indexes | migration | PASS |
| audit_logs table + 3 indexes | migration | PASS |
| UsageEvent entity — all fields | `domain/entities/usage_event.py` | PASS |
| AuditLog entity — all fields | `domain/entities/audit_log.py` | PASS |
| AuditAction — 14 constants | `domain/entities/audit_log.py` | PASS |
| UsageRepository port | `domain/ports/usage_repository.py` | PASS |
| AuditRepository port — append-only | `domain/ports/audit_repository.py` | PASS |

### Phase 2 — Infrastructure

| Item | File | Result |
|------|------|--------|
| SQLAlchemyUsageRepository | `infrastructure/persistence/repositories/usage_repository.py` | PASS |
| SQLAlchemyAuditRepository | `infrastructure/persistence/repositories/audit_repository.py` | PASS |

### Phase 3 — Fakes

| Item | File | Result |
|------|------|--------|
| FakeUsageRepository | `tests/fakes/fake_usage_repository.py` | PASS |
| FakeAuditRepository | `tests/fakes/fake_audit_repository.py` | PASS |

### Phase 4 — Services

| Item | Verification | Result |
|------|-------------|--------|
| UsageService.record() — synchronous | Awaited directly in DocumentService | PASS |
| UsageService.record() — swallows exceptions | `test_record_failure_is_swallowed_not_raised` | PASS |
| UsageService.record() — optional template_id | `test_record_without_template_id_is_allowed` | PASS |
| AuditService.log() — fire-and-forget | Uses `asyncio.create_task()` | PASS |
| AuditService._write() — swallows exceptions | `test_log_failure_is_swallowed` | PASS |
| IP extracted in presentation layer only | Service has no FastAPI import | PASS |

### Phase 5 — Service Integration

| Integration point | Spec requirement | Result |
|-------------------|-----------------|--------|
| generate_single → usage record("single", 1) | After doc_repo.create() | PASS |
| generate_single → audit DOCUMENT_GENERATE | After doc_repo.create() | PASS |
| generate_bulk → usage record("bulk", success_count) | Only if success_count > 0 | PASS |
| generate_bulk → audit DOCUMENT_GENERATE_BULK + details | Single entry with counts | PASS |
| delete_document → audit DOCUMENT_DELETE | Present | PASS |
| No audit/usage on template error paths | Verified in tests | PASS |
| Both services optional (None default) | Constructor signature | PASS |
| TemplateService — 5 audit integration points | upload, version, delete, share, unshare | PASS |

### Phase 6 — Router Direct Audit Calls

| Router | Action | Result |
|--------|--------|--------|
| auth.py login | AUTH_LOGIN + ip_address | PASS |
| auth.py change-password | AUTH_CHANGE_PASSWORD + ip_address | PASS |
| users.py create | USER_CREATE + details | PASS |
| users.py update | USER_UPDATE + sanitized details | PASS |
| users.py deactivate | USER_DEACTIVATE | PASS |

### Phase 7 — API Endpoints

| Endpoint | Auth | Result |
|----------|------|--------|
| GET /api/v1/usage | any auth user | PASS |
| GET /api/v1/usage — default year/month | current month | PASS |
| GET /api/v1/usage/tenant | admin-only (403 for non-admin) | PASS |
| GET /api/v1/audit | admin-only (403 for non-admin) | PASS |
| GET /api/v1/audit — pagination (size ≤ 100) | validated | PASS |
| GET /api/v1/audit — action filter | works | PASS |
| Both routers registered in main.py | lines 49–50 | PASS |

### Architecture

| Concern | Result |
|---------|--------|
| Domain entities — no framework imports | PASS |
| Services — domain only, no FastAPI | PASS |
| No circular imports (TYPE_CHECKING guard) | PASS |
| Append-only ports (no update/delete methods) | PASS |

### Frontend

| Feature | Files | Result |
|---------|-------|--------|
| UsageWidget (user monthly count) | `features/usage/components/UsageWidget.tsx` | PASS |
| TenantUsageTable (admin breakdown) | `features/usage/components/TenantUsageTable.tsx` | PASS |
| useMyUsage + useTenantUsage hooks | `features/usage/api/queries.ts` | PASS |
| AuditLogTable + pagination | `features/audit/components/AuditLogTable.tsx` | PASS |
| AuditFilters component | `features/audit/components/AuditFilters.tsx` | PASS |
| useAuditLog hook + filters | `features/audit/api/queries.ts` | PASS |

---

## WARNING Items

### WARNING-1 — Frontend audit URL mismatch (runtime bug)

**Severity**: WARNING — visible runtime defect when user visits audit log page.

| Side | Value |
|------|-------|
| Frontend calls | `/audit-log?...` (`features/audit/api/queries.ts` line 39) |
| Backend serves | `/api/v1/audit` (`main.py` line 50) |
| Spec defines | `GET /api/v1/audit-log` |

The spec defines `audit-log` as the path. The frontend correctly follows the spec. The backend diverges by using `/audit`. At runtime the frontend will receive **404**.

**Fix** (one-liner in main.py):
```python
# Before
app.include_router(audit.router, prefix=f"{settings.api_v1_prefix}/audit", tags=["audit"])
# After
app.include_router(audit.router, prefix=f"{settings.api_v1_prefix}/audit-log", tags=["audit"])
```

---

### WARNING-2 — UsageRepository port method names differ from spec

**Severity**: WARNING — internal divergence only; no runtime impact.

| Spec | Implementation |
|------|---------------|
| `get_monthly_stats_for_user(user_id, tenant_id, year, month)` | `get_user_month_total(user_id, month_start: date)` |
| `get_monthly_stats_for_tenant(tenant_id, year, month)` | `get_tenant_month_total(month_start: date)` + `get_tenant_user_breakdown(month_start: date)` |

The implementation splits the tenant method into total + breakdown, which is cleaner and all tests pass. Spec signatures were illustrative. Recommend updating spec to match implementation.

---

### WARNING-3 — AuditAction user_delete vs user.deactivate

**Severity**: WARNING — naming divergence only; consistent throughout implementation.

| Spec constant name | Implementation |
|--------------------|---------------|
| `user_delete` | `USER_DEACTIVATE = "user.deactivate"` |

The operation is a soft delete (is_active=False), not a hard delete. `user.deactivate` accurately reflects the semantic. The spec should be updated to use `user_delete → user.deactivate`.

---

## CRITICAL Items

None.

---

## Recommendation

Fix WARNING-1 (audit URL) before shipping. It is a one-line change in `backend/src/app/main.py`. WARNING-2 and WARNING-3 require only spec document updates — no code changes.
