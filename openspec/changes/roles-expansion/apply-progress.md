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

## Phase 2 — Infrastructure (PENDING)

T-INFRA-01 through T-INFRA-06 — not started.

## Phase 3 — Application Service / Auth Flow (PENDING)

T-APP-01 through T-APP-03 — not started.

## Phase 4 — Presentation (PENDING)

T-PRES-01 through T-PRES-10 — not started.

## Phase 5 — Frontend (PENDING)

T-FE-01 through T-FE-06 — not started.

## Phase 6 — Regression Gate (PENDING)

T-REG-01 through T-REG-03 — not started.

## Phase 7 — Operational (PENDING)

T-OPS-01 through T-OPS-02 — not started.
