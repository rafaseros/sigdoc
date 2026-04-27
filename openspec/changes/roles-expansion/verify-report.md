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

---

## Phase 2 Verification

**Change**: roles-expansion
**Phase verified**: Phase 2 — Infrastructure (T-INFRA-01..06)
**Mode**: Strict TDD
**Verdict**: APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phase 2) | 6 |
| Tasks complete | 6 |
| Tasks incomplete | 0 |

All Phase 2 tasks checked off: T-INFRA-01, T-INFRA-02, T-INFRA-03, T-INFRA-04, T-INFRA-05, T-INFRA-06.

---

### Build & Tests Execution

**Build**: N/A (Python — no compile step)

**Phase 2 targeted tests (run in isolation)**:
```
tests/integration/test_role_migration.py    9 items   → 9 passed
tests/unit/infrastructure/test_user_model_defaults.py  2 items → 2 passed
tests/unit/test_middleware.py              13 items   → 13 passed
```

**Full suite**:
```
506 passed, 32 warnings in 19.97s
0 failed, 0 errors
```

Delta vs Phase 1 baseline (495): +11 new tests. Matches apply-progress claim exactly.

**Coverage**: Not run (not required for Phase 2 infra-only scope)

---

### TDD Compliance

| Task | RED evidence | GREEN |
|------|-------------|-------|
| T-INFRA-01 | Verification-only (no test) | `010` confirmed latest, `011` slot was free |
| T-INFRA-04 | 2 FAIL (`col.default.arg == 'user'`) | 2 PASS after T-INFRA-05 |
| T-INFRA-05 | — | Both `default` and `server_default` → `"document_generator"` |
| T-INFRA-02 | 9 FAIL (`FileNotFoundError: 011_role_expansion.py`) | 9 PASS after T-INFRA-03 |
| T-INFRA-03 | — | Migration created + applied; DB at `011 (head)` |
| T-INFRA-06 | 1 FAIL (`'user' != 'document_generator'`) | 1 PASS + all 13 middleware tests GREEN |

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-ROLE-02: migrate user→template_creator | SCEN-ROLE-01: upgrade transforms rows | `test_role_migration.py::TestUpgradeOrder::test_upgrade_execute_sets_template_creator` | ✅ COMPLIANT |
| REQ-ROLE-02: migration order (ADR-ROLE-02) | SCEN-ROLE-01: UPDATE before ALTER DEFAULT | `test_role_migration.py::TestUpgradeOrder::test_upgrade_calls_execute_before_alter_column` | ✅ COMPLIANT |
| REQ-ROLE-02: upgrade sets document_generator default | SCEN-ROLE-01: new users get least-privilege | `test_role_migration.py::TestUpgradeOrder::test_upgrade_alter_column_sets_document_generator_default` | ✅ COMPLIANT |
| REQ-ROLE-03: downgrade collapses both roles | SCEN-ROLE-02: lossy rollback | `test_role_migration.py::TestDowngradeOrder::test_downgrade_execute_collapses_both_new_roles` | ✅ COMPLIANT |
| REQ-ROLE-03: downgrade order (ADR-ROLE-02) | SCEN-ROLE-02: ALTER DEFAULT before UPDATE | `test_role_migration.py::TestDowngradeOrder::test_downgrade_calls_alter_column_before_execute` | ✅ COMPLIANT |
| REQ-ROLE-03: downgrade restores user default | SCEN-ROLE-02: server_default reverts | `test_role_migration.py::TestDowngradeOrder::test_downgrade_alter_column_restores_user_default` | ✅ COMPLIANT |
| REQ-ROLE-03: metadata integrity | SCEN-ROLE-02: correct revision chain | `test_role_migration.py::TestMigrationMetadata::test_revision_is_011` + `test_down_revision_is_010` | ✅ COMPLIANT |
| REQ-ROLE-05: ORM Python default | UserModel.role default == 'document_generator' | `test_user_model_defaults.py::test_python_default_is_document_generator` | ✅ COMPLIANT |
| REQ-ROLE-05: ORM server default | UserModel.role server_default == 'document_generator' | `test_user_model_defaults.py::test_server_default_is_document_generator` | ✅ COMPLIANT |
| ADR-ROLE-03: middleware safe-default | Stale token (no role claim) → document_generator | `test_middleware.py::TestGetCurrentUserValid::test_default_role_is_document_generator` | ✅ COMPLIANT |

**Compliance summary**: 10/10 Phase 2 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| `UserModel.role` `default="document_generator"` | ✅ Implemented | `models/user.py:19` — confirmed |
| `UserModel.role` `server_default="document_generator"` | ✅ Implemented | `models/user.py:19` — same column definition |
| Migration `011_role_expansion.py` exists | ✅ Implemented | `alembic/versions/011_role_expansion.py` |
| `revision = "011"` | ✅ Correct | Line 35 confirmed |
| `down_revision = "010"` | ✅ Correct | Line 36 confirmed — only one migration has `down_revision="010"` (no branch) |
| `upgrade()`: `op.execute` before `op.alter_column` | ✅ Correct | Lines 45 then 49 — matches ADR-ROLE-02 |
| `downgrade()`: `op.alter_column` before `op.execute` | ✅ Correct | Lines 61 then 69 — matches ADR-ROLE-02 |
| Downgrade lossy behavior documented in docstring | ✅ Correct | Module docstring explicitly says "LOSSY" and explains the caveat |
| Column type stays `String(20)` | ✅ Correct | `existing_type=sa.String(20)` in both upgrade/downgrade — no schema change |
| `tenant.py:44` fallback → `"document_generator"` | ✅ Implemented | `role=payload.get("role", "document_generator")` at line 44 |
| W-1 (test_middleware.py:83) closed | ✅ Closed | Test renamed to `test_default_role_is_document_generator`, asserts `"document_generator"` at line 88 |
| `signup_service.py role="admin"` untouched | ✅ Confirmed | Lines 129 and 162 still `role="admin"` — out of Phase 2 scope |
| `user_repository.py SQL filter` untouched | ✅ Confirmed | Line 84 still `UserModel.role == "admin"` — out of Phase 2 scope |
| No presentation/frontend/application changes | ✅ Confirmed | Only infra/migration/middleware files touched |

---

### Live DB Verification

| Check | Result |
|-------|--------|
| `alembic current` | `011 (head)` ✅ |
| `role` column server default | `'document_generator'::character varying` ✅ |
| Column type | `character varying(20)` — unchanged ✅ |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-ROLE-02: `revision="011"`, `down_revision="010"` | ✅ Yes | Exact match |
| ADR-ROLE-02: `upgrade()` UPDATE before ALTER DEFAULT | ✅ Yes | `op.execute` on line 45, `op.alter_column` on line 49 |
| ADR-ROLE-02: `downgrade()` ALTER DEFAULT before UPDATE | ✅ Yes | `op.alter_column` on line 61, `op.execute` on line 69 |
| ADR-ROLE-02: Column type unchanged (`String(20)`) | ✅ Yes | `existing_type=sa.String(20)` in both directions |
| ADR-ROLE-03: `UserModel.role` both defaults → `document_generator` | ✅ Yes | `default` + `server_default` both set |
| ADR-ROLE-03: `tenant.py:44` fallback → `document_generator` | ✅ Yes | Confirmed at line 44 |
| Phase 2 scope: infra + middleware only, no app/presentation/frontend | ✅ Yes | Clean boundary maintained |
| Migration test strategy: mock `alembic.op` to verify SQL order | ✅ Yes | `test_role_migration.py` uses direct `alembic.op` patching |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
None. W-1 from Phase 1 verify is fully resolved — `test_middleware.py:83` now asserts `"document_generator"` and passes.

**SUGGESTION**:
- The migration test `test_docstring_mentions_lossy` (line 81–86) has a logic bug in its assertion: `assert "lossy" in doc.lower() or "lossless" not in doc.lower()`. The second branch (`"lossless" not in doc.lower()`) is trivially True for any docstring that doesn't contain the word "lossless", making the test pass even if the docstring doesn't mention "lossy". The test effectively never fails. This is non-blocking since the docstring DOES contain "lossy" (first branch is True), but the assertion logic should be tightened to `assert "lossy" in doc.lower()` alone for correctness. Non-blocking — coverage intent is met.

---

### Test Counts

| Metric | Value |
|--------|-------|
| Phase 1 baseline | 495 |
| After Phase 2 | 506 |
| Net new (Phase 2) | +11 |
| Breakdown | `test_role_migration.py`: 9 new + `test_user_model_defaults.py`: 2 new + `test_middleware.py`: 1 updated (W-1 fix, renamed not new) |
| Failures | 0 |
| Regressions | 0 |

---

### Verdict

**APPROVED**

Phase 2 is complete, correct, and coherent. All 6 infrastructure tasks implemented following strict TDD. 506 tests pass, 0 failures, 0 regressions. Live DB confirmed at `011 (head)` with `role` server default `'document_generator'`. The W-1 WARNING from Phase 1 verify (test_middleware.py:83) is fully closed. The scope boundary (infra/migration/middleware only) was respected. One non-blocking suggestion about a loose test assertion logic in the migration test docstring check.

Phase 3 (T-APP-01..03) may proceed.
