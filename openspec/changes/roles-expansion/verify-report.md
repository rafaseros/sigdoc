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

---

## Phase 3 Verification

**Change**: roles-expansion
**Phase verified**: Phase 3 — Application Service / Auth Flow (T-APP-01..03)
**Mode**: Strict TDD
**Verdict**: APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phase 3) | 3 |
| Tasks complete | 3 |
| Tasks incomplete | 0 |

All Phase 3 tasks checked off: T-APP-01, T-APP-02, T-APP-03.

---

### Build & Tests Execution

**Build**: N/A (Python — no compile step)

**Phase 3 targeted tests (run in isolation)**:
```
tests/integration/test_auth_refresh_role.py    2 items
2 passed in 0.34s
```

**Full suite**:
```
508 passed, 37 warnings in 20.07s
0 failed, 0 errors
```

Delta vs Phase 2 baseline (506): +2 new tests. Matches apply-progress claim exactly.

**Coverage**: Not run (not required for Phase 3 scope)

---

### TDD Compliance

| Task | RED evidence | GREEN |
|------|-------------|-------|
| T-APP-01 | FAIL — handler returned role='user' (fallback default) instead of 'template_creator' from DB | PASS after T-APP-03 |
| T-APP-02 | FAIL — HTTP 200 instead of 401 (handler had no user-existence check) | PASS after T-APP-03 |
| T-APP-03 | — | Handler fixed; both T-APP-01 and T-APP-02 GREEN |

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-ROLE-09: refresh reads role from DB | SCEN-ROLE-06: promoted user gets updated role | `test_auth_refresh_role.py::test_refresh_returns_db_role_after_promotion` | ✅ COMPLIANT |
| REQ-ROLE-10: refresh rejects deleted user | SCEN-ROLE-07: deleted user → 401 | `test_auth_refresh_role.py::test_refresh_returns_401_for_deleted_user` | ✅ COMPLIANT |
| Regression: existing refresh test | valid token → 200 | `test_auth_api.py::test_refresh_with_valid_token_returns_200` | ✅ COMPLIANT |

**Compliance summary**: 3/3 Phase 3 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| `payload.get("role", ...)` absent from `/auth/refresh` handler | ✅ Confirmed | `grep -n "payload.get.*role"` on auth.py → no output |
| `repo.get_by_id(UUID(sub))` called in handler | ✅ Confirmed | Line 161: `user = await repo.get_by_id(_UUID(payload["sub"]))` |
| `user is None or not user.is_active` guard raises HTTP 401 | ✅ Confirmed | Lines 163–167 |
| `role=user.role` used when minting access token | ✅ Confirmed | Line 173: `role=user.role,  # always from DB, never from token payload` |
| `AsyncSession = Depends(get_session)` injected into handler | ✅ Confirmed | Line 137 of handler signature |
| `SQLAlchemyUserRepository` imported at module level | ✅ Confirmed | Line 19 of auth.py imports |
| `test_refresh_with_valid_token_returns_200` updated with monkeypatch | ✅ Confirmed | Lines 130–165 of test_auth_api.py — monkeypatches repo, seeds user with is_active=True |
| `test_auth_refresh_role.py` has SCEN-ROLE-06 test | ✅ Confirmed | `test_refresh_returns_db_role_after_promotion` — decodes new access token, asserts `payload["role"] == "template_creator"` |
| `test_auth_refresh_role.py` has SCEN-ROLE-07 test | ✅ Confirmed | `test_refresh_returns_401_for_deleted_user` — asserts status 401 AND `"access_token" not in data` |
| No domain layer changes (Phase 1 intact) | ✅ Confirmed | `permissions.py` and `user.py` entity unchanged |
| No infrastructure changes (Phase 2 intact) | ✅ Confirmed | `UserModel.role` defaults, `011_role_expansion.py`, `tenant.py` all intact |
| No presentation/schema changes | ✅ Confirmed | Only `auth.py` touched |
| No frontend changes | ✅ Confirmed | git diff confirms zero frontend files modified in Phase 3 commits |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-ROLE-01: sequence — decode → validate type=refresh → fetch user → 401 if missing/inactive → mint token | ✅ Yes | Exact sequence at lines 146–179 |
| ADR-ROLE-01: `payload.get("role", "user")` bug eliminated | ✅ Yes | Confirmed absent via static analysis |
| ADR-ROLE-01: backward compatible (refresh tokens without role claim still work) | ✅ Yes | Refresh tokens never carry role in this codebase; the claim was never there to begin with |
| ADR-TEST-01: new test file `tests/integration/test_auth_refresh_role.py` | ✅ Yes | File exists, 2 tests |
| ADR-TEST-01: pattern matches existing auth tests (monkeypatch SQLAlchemyUserRepository) | ✅ Yes | Uses same `_make_repo_class` pattern as `test_auth_api.py` |
| Phase 3 scope: auth.py only + 1 new test file + 1 updated test | ✅ Yes | Clean boundary maintained |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
None.

**SUGGESTION**:
- `test_refresh_with_valid_token_returns_200` (line 67) still constructs the user with `role="user"` (the legacy role value). Since the handler reads `user.role` from DB and returns it in the token, this means the test inadvertently verifies that a legacy `"user"` role value propagates through the refresh flow. It passes because the test only checks `status_code == 200` and `"access_token" in data` — it does not decode the token. This is non-blocking (the test remains valid), but adding a role assertion `assert payload["role"] == "user"` or updating the role to `"document_generator"` would make the test self-documenting. Non-blocking.

---

### Test Counts

| Metric | Value |
|--------|-------|
| Phase 2 baseline | 506 |
| After Phase 3 | 508 |
| Net new (Phase 3) | +2 |
| Breakdown | `test_auth_refresh_role.py`: 2 new tests (SCEN-ROLE-06, SCEN-ROLE-07); `test_auth_api.py`: 1 existing test updated (no new count) |
| Failures | 0 |
| Regressions | 0 |

---

### Verdict

**APPROVED**

Phase 3 is complete, correct, and coherent. Both auth flow tasks implemented following strict TDD. 508 tests pass, 0 failures, 0 regressions. The `/auth/refresh` handler correctly re-fetches the user from DB via `repo.get_by_id`, returns HTTP 401 for missing/inactive users, and derives `role` exclusively from the DB row — the `payload.get("role", ...)` bug is fully eliminated. REQ-ROLE-09 and REQ-ROLE-10 are satisfied with behavioral test evidence. Phase 1 and Phase 2 work is intact with zero regressions.

Phase 4 (T-PRES-01..10) may proceed.
