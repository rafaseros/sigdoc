# Verify Report — roles-expansion

**Change**: roles-expansion
**Phase verified**: Phase 1 — Domain & Permissions (T-DOMAIN-01..06)
**Mode**: Strict TDD
**Verdict**: APPROVED

---

## Phase 1 Verification

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phase 1) | 6 |
| Tasks complete | 6 |
| Tasks incomplete | 0 |

All Phase 1 tasks checked off: T-DOMAIN-01, T-DOMAIN-02, T-DOMAIN-03, T-DOMAIN-04, T-DOMAIN-05, T-DOMAIN-06.

---

### Build & Tests Execution

**Build**: N/A (Python — no compile step; type check deferred to Phase 5 T-REG-03)

**Domain tests (isolated)**:
```
tests/unit/domain/test_permissions.py  40 items
tests/unit/domain/test_user_entity.py   4 items
44 passed in 0.14s
```

**Full suite**:
```
495 passed, 33 warnings in 19.46s
0 failed, 0 errors
```

**Coverage**: Not run (not required for Phase 1 domain-only scope)

---

### TDD Compliance

| Task | RED evidence | GREEN |
|------|-------------|-------|
| T-DOMAIN-01 | Rows PASS immediately — existing helpers return `role == "admin"`, already correct for new roles | 14 new parametrized rows, all PASS |
| T-DOMAIN-02 | — | Audit confirmed, no impl change needed |
| T-DOMAIN-03 | 4 FAIL (`ImportError: cannot import 'can_manage_own_templates'`) | 4 PASS after T-DOMAIN-04 |
| T-DOMAIN-04 | — | Helper added, RED→GREEN via T-DOMAIN-03 |
| T-DOMAIN-05 | 2 FAIL (`'user' != 'document_generator'`) | 4 PASS after T-DOMAIN-06 |
| T-DOMAIN-06 | — | Entity default changed, all GREEN |

TDD note on T-DOMAIN-01: The existing helpers already use `role == "admin"` (False for any non-admin), so adding new role rows to the truth table produces passing tests immediately. This is semantically correct — no implementation change was needed because the helper contract was already correct for new roles. RED cycle was not artificially forced; the value of T-DOMAIN-01 is as a regression lock, not as a failing test.

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-TMP-01: can_manage_own_templates | SCEN-TMP-01: admin=True | `test_permissions.py::test_can_manage_own_templates[admin]` | ✅ COMPLIANT |
| REQ-TMP-01: can_manage_own_templates | SCEN-TMP-01: template_creator=True | `test_permissions.py::test_can_manage_own_templates[template_creator]` | ✅ COMPLIANT |
| REQ-TMP-01: can_manage_own_templates | SCEN-TMP-01: document_generator=False | `test_permissions.py::test_can_manage_own_templates[document_generator]` | ✅ COMPLIANT |
| REQ-TMP-01: can_manage_own_templates | SCEN-TMP-01: unknown=False | `test_permissions.py::test_can_manage_own_templates[unknown]` | ✅ COMPLIANT |
| REQ-ROLE-01: 3-role taxonomy | All admin-only helpers return False for template_creator | `test_permissions.py::*[template_creator]` (7 helpers) | ✅ COMPLIANT |
| REQ-ROLE-01: 3-role taxonomy | All admin-only helpers return False for document_generator | `test_permissions.py::*[document_generator]` (7 helpers) | ✅ COMPLIANT |
| REQ-ROLE-04: User entity default | SCEN-ROLE-09: User() → role == 'document_generator' | `test_user_entity.py::test_default_role_is_document_generator` | ✅ COMPLIANT |
| REQ-ROLE-04: User entity default | Explicit role is preserved | `test_user_entity.py::test_explicit_role_is_preserved` | ✅ COMPLIANT |
| REQ-ROLE-04: User entity default | template_creator accepted | `test_user_entity.py::test_template_creator_role_accepted` | ✅ COMPLIANT |
| REQ-ROLE-04: User entity default | explicit == default for document_generator | `test_user_entity.py::test_document_generator_explicit_equals_default` | ✅ COMPLIANT |

**Compliance summary**: 10/10 Phase 1 scenarios compliant.

Scenarios deferred to later phases (not in scope for Phase 1 verification):
- SCEN-TMP-02..10 (presentation gates, frontend) — Phase 4/5
- SCEN-ROLE-01..08, SCEN-ROLE-10 (migration, schemas, refresh, users API) — Phase 2/3/4

---

### Correctness (Static — Structural Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| `can_manage_own_templates` exists in `permissions.py` | ✅ Implemented | Line 89–96, body `return role in {"admin", "template_creator"}` |
| `can_manage_own_templates` in `__all__` | ✅ Implemented | Line 37 of `__all__` list |
| `User.role` default is `"document_generator"` | ✅ Implemented | `user.py:13` — `role: str = "document_generator"` |
| All 7 existing admin-only helpers use `role == "admin"` | ✅ Verified | No implicit `"user"` logic; new roles return False by design |
| No infrastructure changes (no migration, no ORM edit) | ✅ Confirmed | `UserModel.role` still `default="user"` — Phase 2 scope |
| No presentation changes | ✅ Confirmed | `dependencies.py` unchanged, `templates.py` unchanged |
| No frontend changes | ✅ Confirmed | No files touched under `frontend/` |
| `tenant.py:44` still has `payload.get("role", "user")` | ✅ Confirmed | Phase 2 (T-INFRA-06) scope |
| No `011_role_expansion.py` migration exists | ✅ Confirmed | `alembic/versions/` ends at `010_pdf_export.py` |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-TMP-01: helper body `role in {"admin", "template_creator"}` | ✅ Yes | Exact match |
| ADR-TMP-01: add to `__all__` | ✅ Yes | Present at line 37 |
| ADR-ROLE-03: entity default `"document_generator"` | ✅ Yes | line 13 confirmed |
| ADR-ROLE-03: `tenant.py:44` deferred to Phase 2 | ✅ Yes | Middleware unchanged in Phase 1 |
| Phase 1 scope: domain only, no infra/presentation/frontend | ✅ Yes | Clean scope boundary maintained |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix before Phase 2 proceeds):
- `backend/tests/unit/test_middleware.py:83` asserts `result.role == "user"` for missing-claim fallback. This test CURRENTLY PASSES (middleware still has `"user"` fallback). T-INFRA-06 in Phase 2 WILL change `tenant.py:44` to `payload.get("role", "document_generator")`, which WILL break this test. **Phase 2 agent MUST update this test** when implementing T-INFRA-06 — and must `docker cp` the updated file since `tests/` is not volume-mounted.

**SUGGESTION**:
- The `test_permissions.py` docstring at line 4 still says `"user → False"` (pre-expansion language). This is cosmetically stale — the truth table now has 5 rows including `user`, `template_creator`, `document_generator`. A one-line docstring update would keep the file self-documenting. Non-blocking.

---

### Test Counts

| Metric | Value |
|--------|-------|
| Baseline (pre-Phase 1) | 473 |
| After Phase 1 | 495 |
| Net new | +22 |
| Breakdown | `test_permissions.py`: +18 (7 helpers × 2 new roles + 4 `can_manage_own_templates`) + `test_user_entity.py`: +4 |
| Failures | 0 |
| Regressions | 0 |

---

### Verdict

**APPROVED**

Phase 1 is complete, correct, and coherent. All 6 domain tasks implemented following strict TDD. 495 tests pass, 0 failures, 0 regressions. The scope boundary (domain-only) was respected — no infrastructure, presentation, or frontend changes were made. The single WARNING about `test_middleware.py:83` is a known, pre-flagged risk for Phase 2 and does not block Phase 1 approval.

Phase 2 (T-INFRA-01..06) may proceed.
