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

---

## Phase 4 Verification

**Change**: roles-expansion
**Phase verified**: Phase 4 — Presentation (T-PRES-01..10)
**Mode**: Strict TDD
**Verdict**: APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phase 4) | 10 |
| Tasks complete | 10 |
| Tasks incomplete | 0 |

All Phase 4 tasks checked off: T-PRES-01, T-PRES-02, T-PRES-03, T-PRES-04, T-PRES-05, T-PRES-06, T-PRES-07, T-PRES-08, T-PRES-09, T-PRES-10.

---

### Build & Tests Execution

**Build**: N/A (Python — no compile step)

**Phase 4 targeted tests (run in isolation)**:
```
tests/unit/presentation/test_role_validation.py   7 items  → 7 passed in 0.12s
tests/integration/test_template_endpoint_gates.py 7 items  → 7 passed in 0.34s
tests/integration/test_users_api.py::test_create_user_without_role_defaults_to_document_generator
                                                  1 item   → 1 passed in 0.44s
```

**Full suite**:
```
523 passed, 37 warnings in 20.92s
0 failed, 0 errors
```

Delta vs Phase 3 baseline (508): +15 new tests. Matches apply-progress claim exactly.

**Coverage**: Not run (not required for Phase 4 presentation scope)

---

### TDD Compliance

| Task | RED evidence | GREEN |
|------|-------------|-------|
| T-PRES-01 | 4 FAIL (`template_creator`/`document_generator` not accepted; `user` not rejected) | 7 PASS after T-PRES-02 |
| T-PRES-02 | — | Schema allow-list updated to 3-role set; all 7 unit tests GREEN |
| T-PRES-03 | 1 FAIL (`role` was `"user"` instead of `"document_generator"`) | 1 PASS after T-PRES-04 |
| T-PRES-04 | — | `users.py:65` updated to `role="document_generator"`; all 8 users tests GREEN |
| T-PRES-05 | — | `require_template_manager` added; behavior coverage via T-PRES-06..10 |
| T-PRES-06 | 1 FAIL (got 201, expected 403 — no gate yet) | PASS after T-PRES-09 |
| T-PRES-07..08 | Some gates already worked via service layer (correct 403/201) | All 7 gate tests GREEN after T-PRES-09 |
| T-PRES-09 | — | Gates wired; all 7 template gate tests GREEN |
| T-PRES-10 | — | Generate tests SCEN-TMP-07/08 PASS (no new gate; service layer enforces) |

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-ROLE-06: UpdateUserRequest 3-role validator | SCEN-ROLE-03: `document_generator` accepted | `test_role_validation.py::test_valid_roles_are_accepted[document_generator]` | ✅ COMPLIANT |
| REQ-ROLE-06: UpdateUserRequest 3-role validator | SCEN-ROLE-03: `template_creator` accepted | `test_role_validation.py::test_valid_roles_are_accepted[template_creator]` | ✅ COMPLIANT |
| REQ-ROLE-06: UpdateUserRequest 3-role validator | SCEN-ROLE-04: legacy `"user"` rejected with 422 | `test_role_validation.py::test_legacy_user_role_is_rejected` | ✅ COMPLIANT |
| REQ-ROLE-06: UpdateUserRequest 3-role validator | SCEN-ROLE-10: invalid value → error names 3 allowed values | `test_role_validation.py::test_invalid_role_value_rejected_with_allowed_values_in_message` | ✅ COMPLIANT |
| REQ-ROLE-08: POST /users default role | SCEN-ROLE-05: no role → 201, role=document_generator | `test_users_api.py::test_create_user_without_role_defaults_to_document_generator` | ✅ COMPLIANT |
| REQ-TMP-02: require_template_manager dependency | ADR-TMP-02: pre-bound via require_capability | `dependencies.py` static — `require_template_manager = require_capability(can_manage_own_templates)` | ✅ COMPLIANT |
| REQ-TMP-03: upload endpoint gated | SCEN-TMP-02: document_generator → 403 | `test_template_endpoint_gates.py::test_document_generator_cannot_upload_template` | ✅ COMPLIANT |
| REQ-TMP-03: upload endpoint gated | SCEN-TMP-03: template_creator → 201 | `test_template_endpoint_gates.py::test_template_creator_can_upload_template` | ✅ COMPLIANT |
| REQ-TMP-03: upload endpoint gated | SCEN-TMP-04: admin → 201 | `test_template_endpoint_gates.py::test_admin_can_upload_template` | ✅ COMPLIANT |
| REQ-TMP-04: versions endpoint gated | SCEN-TMP-05: document_generator → 403 | `test_template_endpoint_gates.py::test_document_generator_cannot_upload_new_version` | ✅ COMPLIANT |
| REQ-TMP-04: versions endpoint gated | SCEN-TMP-06: template_creator (owner) → 201 | `test_template_endpoint_gates.py::test_template_creator_can_upload_new_version_on_own_template` | ✅ COMPLIANT |
| REQ-TMP-05: generate endpoints ungated | SCEN-TMP-07: document_generator + shared template → 201 | `test_template_endpoint_gates.py::test_document_generator_generates_from_shared_template` | ✅ COMPLIANT |
| REQ-TMP-05: generate endpoints ungated | SCEN-TMP-08: document_generator + non-shared → 403 | `test_template_endpoint_gates.py::test_document_generator_blocked_from_non_shared_template` | ✅ COMPLIANT |

**Compliance summary**: 13/13 Phase 4 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| `require_template_manager` in `dependencies.py` | ✅ Implemented | Line 61: `require_template_manager = require_capability(can_manage_own_templates)` |
| `can_manage_own_templates` imported in `dependencies.py` | ✅ Implemented | Line 19 imports it from `app.domain.services.permissions` |
| Pattern matches `require_user_manager`, `require_audit_viewer`, `require_tenant_usage_viewer` | ✅ Confirmed | All four are `require_capability(...)` pre-bound; consistent pattern |
| `POST /templates/upload` uses `Depends(require_template_manager)` | ✅ Implemented | `templates.py:100` — `current_user: CurrentUser = Depends(require_template_manager)` |
| `POST /templates/{template_id}/versions` uses `Depends(require_template_manager)` | ✅ Implemented | `templates.py:161` — same pattern |
| DELETE/UPDATE/GET template endpoints NOT gated with `require_template_manager` | ✅ Confirmed | DELETE (line 340), GET (line 280), shares (lines 369, 413, 434) all use `Depends(get_current_user)` |
| `UpdateUserRequest.validate_role` allow-list = 3-role set | ✅ Implemented | `schemas/user.py:33` — `if v not in ("admin", "template_creator", "document_generator")` |
| Error message names all 3 allowed values (Spanish) | ✅ Implemented | `"El rol debe ser 'admin', 'template_creator' o 'document_generator'"` |
| `CreateUserRequest` has no `role` field | ✅ Confirmed | Only `email`, `full_name`, `password` fields; no role field added |
| `POST /users` handler: `role="document_generator"` explicit assignment | ✅ Implemented | `users.py:65` — `role="document_generator"` in `UserModel(...)` constructor |
| `POST /documents/generate` has no `require_template_manager` | ✅ Confirmed | `documents.py:76` — only `Depends(get_current_user)` |
| `POST /documents/generate-bulk` has no `require_template_manager` | ✅ Confirmed | `documents.py:150` — only `Depends(get_current_user)` |
| Pre-flight fixture migration: 13 `role="user"` fixtures updated | ✅ Confirmed | `test_users_api.py` (8 changes) + `test_templates_api.py` (5 changes) |
| `test_pdf_export.py` `_make_non_admin_user()` `role="user"` intentionally NOT migrated | ✅ Confirmed | Creates `CurrentUser` directly; bypasses schema; tests download RBAC, not role taxonomy |
| Phase 1-3 work intact (no regressions) | ✅ Confirmed | Full suite 523 passing, 0 failing |
| No migration changes in Phase 4 | ✅ Confirmed | Still at `011 (head)` — no new migration files |
| No frontend changes in Phase 4 | ✅ Confirmed | Phase 4 is backend-only; frontend deferred to Phase 5 |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-TMP-02: `require_template_manager = require_capability(can_manage_own_templates)` | ✅ Yes | Exact pattern; mirrors other pre-bound deps |
| ADR-TMP-03: gate `POST /upload` and `POST /{id}/versions` only | ✅ Yes | DELETE/GET/shares left with `get_current_user` |
| ADR-TMP-03: DELETE/UPDATE excluded — ownership check in service already excludes document_generator | ✅ Yes | Confirmed — service raises `TemplateAccessDeniedError` for non-owners |
| ADR-ROLE-04: `UpdateUserRequest.validate_role` → 3-role set | ✅ Yes | `("admin", "template_creator", "document_generator")` |
| ADR-ROLE-04: `CreateUserRequest` NOT modified | ✅ Yes | No `role` field in `CreateUserRequest` |
| ADR-ROLE-05: `users.py:65` → explicit `role="document_generator"` assignment | ✅ Yes | Explicit assignment visible in handler |
| ADR-TMP-01: 13 pre-flight fixture migrations | ✅ Yes | Both flagged test files updated; `test_pdf_export.py` intentionally excluded |

---

### Outstanding Fixture Drift (INFO — not blocking)

The following test files still contain `role="user"` in `User(...)` or `CurrentUser(...)` direct constructions. These bypass schema validation and test non-role-related behavior (auth flows, document generation, quota, rate limits, template service unit tests). They are **not incorrect** — the `User` domain entity accepts any string for `role`. However, they represent accumulated technical debt that a follow-up change should address:

- `test_auth_api.py` — 9 occurrences (User domain entity, login/refresh flows)
- `test_template_shares_api.py` — 4 occurrences (CurrentUser overrides)
- `test_document_service.py` — 3 occurrences (service unit tests)
- `test_documents_api.py` — 4 occurrences (CurrentUser overrides)
- `test_template_service.py` — 7 occurrences (service unit tests)
- Others: `test_quota_service.py`, `test_audit_api.py`, `test_tiers_api.py`, `test_rate_limit.py`, etc.

None of these affect passing behavior (full suite: 523/523). They are classified as SUGGESTION only.

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
None.

**SUGGESTION**:
- 31 remaining `role="user"` references across non-Phase-4 test files (`test_auth_api.py`, `test_template_service.py`, `test_documents_api.py`, etc.) are all direct `User(...)` or `CurrentUser(...)` constructions that bypass schema validation. They do not cause failures today but represent fixture drift. A clean-up pass in a follow-up change would improve test self-documentation. Non-blocking.
- The `_FORBIDDEN_DETAIL` constant in `dependencies.py` is `"Solo administradores pueden realizar esta acción"` — also used for `require_template_manager` denials, which are not strictly admin-only. Noted in design (ADR-TMP-02 open question); cosmetic only. Non-blocking.

---

### Test Counts

| Metric | Value |
|--------|-------|
| Phase 3 baseline | 508 |
| After Phase 4 | 523 |
| Net new (Phase 4) | +15 |
| Breakdown | `test_role_validation.py` (NEW): +7 unit tests; `test_users_api.py`: +1 integration test (SCEN-ROLE-05); `test_template_endpoint_gates.py` (NEW): +7 integration tests (SCEN-TMP-02..08) |
| Fixture migrations (not new tests) | 13 (8 in `test_users_api.py` + 5 in `test_templates_api.py`) |
| Failures | 0 |
| Regressions | 0 |

---

### Verdict

**APPROVED**

Phase 4 is complete, correct, and coherent. All 10 presentation tasks implemented following strict TDD. 523 tests pass, 0 failures, 0 regressions. REQ-ROLE-06 (Literal schema validator), REQ-ROLE-08 (default-on-create), REQ-TMP-02 (require_template_manager helper), REQ-TMP-03 (upload gate), REQ-TMP-04 (versions gate), and REQ-TMP-05 (generate ungated) are all satisfied with behavioral test evidence. Phase 1–3 work is fully intact. No migration, no frontend changes.

Phase 5 (T-FE-01..06) may proceed.

---

## Phase 5 Verification

**Change**: roles-expansion
**Phase verified**: Phase 5 — Frontend (T-FE-01..06)
**Mode**: Standard (frontend — no test runner; typecheck + lint only)
**Verdict**: APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phase 5) | 6 |
| Tasks complete | 6 |
| Tasks incomplete | 0 |

All Phase 5 tasks checked off: T-FE-01, T-FE-02, T-FE-03, T-FE-04, T-FE-05, T-FE-06.

---

### Build & Tests Execution

**TypeScript** (`npx tsc --noEmit -p tsconfig.app.json`): ✅ Exit 0 — no errors

**Lint** (`npm run lint`): ✅ Exit 0 — 0 errors, 4 warnings (pre-existing baseline)
```
badge.tsx:52   warning  react-refresh/only-export-components (pre-existing)
button.tsx:58  warning  react-refresh/only-export-components (pre-existing)
tabs.tsx:80    warning  react-refresh/only-export-components (pre-existing)
auth.tsx:80    warning  react-refresh/only-export-components (pre-existing)
```
No new warnings introduced by Phase 5 files (`permissions.ts`, `role-labels.ts` are utility modules with no component exports; they do not trigger the react-refresh rule).

**Backend suite** (no backend changes in Phase 5 — regression check):
```
523 passed, 34 warnings in 21.36s
0 failed, 0 errors
```
Zero regressions. Backend baseline unchanged from Phase 4.

**Frontend test runner**: Not available (per ADR-TEST-01 and tasks.md: "Frontend: Manual + typecheck + lint (no test runner)"). Behavioral verification via static analysis below.

---

### Structural Evidence (per checklist item)

#### 1. `frontend/src/shared/lib/permissions.ts` (T-FE-01) ✅
- File exists at the exact path.
- Exports `Role` type as `"admin" | "template_creator" | "document_generator"` (line 1).
- Exports `canUploadTemplates`, `canManageUsers`, `canViewAudit`, `canViewTenantUsage` — all four present (lines 6–16).
- Each function is a single inline boolean expression (`role === "admin" || role === "template_creator"` or `role === "admin"`).
- Comment at lines 3–4: `// NOTE: Authoritative source is backend/src/app/domain/services/permissions.py.` — points to backend as the authoritative source (REQ-TMP-06 ✅).

#### 2. `frontend/src/shared/lib/role-labels.ts` (T-FE-02) ✅
- Exports `ROLE_LABELS: Record<Role, string>` with correct Spanish mappings:
  - `admin` → `"Administrador"` ✅
  - `template_creator` → `"Creador de plantillas"` ✅
  - `document_generator` → `"Generador de documentos"` ✅
- Exports `getRoleLabel(role: string | undefined): string` (lines 9–12) with `"Usuario"` fallback for `undefined` and unknown values (REQ-TMP-08 ✅).
- **Naming note**: Design ADR-FE-02 used `roleLabel` as the helper name; apply phase used `getRoleLabel`. The actual function is `getRoleLabel`, consistently used in `_authenticated.tsx` (line 79: `getRoleLabel(user?.role)`). The deviation is cosmetic — the contract (fallback `"Usuario"`, type signature) is identical. No inconsistency across usages.

#### 3. `UploadTemplateDialog` conditional render (T-FE-03) ✅
- File: `frontend/src/routes/_authenticated/templates/index.tsx` line 42.
- Implementation: `{canUploadTemplates(user?.role) && <UploadTemplateDialog />}` — JSX short-circuit, not CSS hide.
- For `document_generator`: `canUploadTemplates("document_generator")` → `false` → element is NOT rendered → absent from DOM (SCEN-TMP-09 ✅).
- For `template_creator`/`admin`: returns `true` → element IS rendered (SCEN-TMP-10 ✅).
- `canUploadTemplates` imported from `@/shared/lib/permissions` (line 6) — correct import (REQ-TMP-07 ✅).

#### 4. `EditUserDialog` Select (T-FE-04) ✅
- File: `frontend/src/features/users/components/EditUserDialog.tsx` lines 128–133.
- Three `<SelectItem>` elements present:
  - `value="admin"` with `{ROLE_LABELS.admin}` → `"Administrador"` ✅
  - `value="template_creator"` with `{ROLE_LABELS.template_creator}` → `"Creador de plantillas"` ✅
  - `value="document_generator"` with `{ROLE_LABELS.document_generator}` → `"Generador de documentos"` ✅
- `ROLE_LABELS` imported from `@/shared/lib/role-labels` (line 23) ✅.
- Legacy `"user"` option: ABSENT from the SelectContent — removed ✅.
- `onValueChange={(v) => setRole(v ?? "document_generator")}` — fallback present (line 124) ✅.
- `canEditRole` guard (`isAdmin && !isEditingSelf`) wraps the entire Select block — admin-only editing preserved (REQ-TMP-10 ✅).

#### 5. Role badge pill in `_authenticated.tsx` (T-FE-05) ✅
- File: `frontend/src/routes/_authenticated.tsx` lines 78–80.
- `<Badge variant="secondary" className="text-xs">{getRoleLabel(user?.role)}</Badge>` — exact pattern.
- Uses `getRoleLabel` (imported at line 7) ✅.
- `variant="secondary"` ✅, `className="text-xs"` ✅.
- Falls back to `"Usuario"` for missing/unknown role (via `getRoleLabel` implementation) ✅.
- Badge is inside the header `<div className="flex items-center gap-3">` next to the email span (line 75–80) ✅ (REQ-TMP-09 ✅).

#### 6. Navigation tabs guard (T-FE-06) ✅ (no code change needed — verified)
- `isAdmin = user?.role === "admin"` (line 28).
- `/users` link (line 44): wrapped in `{isAdmin && ...}` ✅ — hidden for `template_creator` and `document_generator`.
- `/audit` link (line 64): wrapped in `{isAdmin && ...}` ✅ — hidden for non-admins.
- `/usage` link (line 52): NOT wrapped with `isAdmin` — intentional, it is an informational page visible to all authenticated users. T-FE-06 listed `/usage` but the design (ADR-FE-04 deferred) and existing codebase never gated it. This matches the codebase intent and was pre-existing before Phase 5.

---

### Spec Compliance Matrix

Note: REQ-TMP-06..10 are frontend requirements. No automated test runner exists for frontend (per ADR-TEST-01). Compliance is established via static structural analysis + typecheck exit 0 as the evidence layer.

| Requirement | Scenario | Evidence | Result |
|-------------|----------|----------|--------|
| REQ-TMP-06: canUploadTemplates helper | `true` for admin/template_creator; `false` for others | `permissions.ts:6–7` — inline boolean; `tsc --noEmit` exit 0 | ✅ COMPLIANT |
| REQ-TMP-07: UploadTemplateDialog conditional | document_generator: element absent from DOM | `templates/index.tsx:42` — `{canUploadTemplates(user?.role) && <UploadTemplateDialog />}` | ✅ COMPLIANT |
| REQ-TMP-07: UploadTemplateDialog conditional | template_creator/admin: element present in DOM | Same expression — short-circuit renders when true | ✅ COMPLIANT |
| REQ-TMP-08: ROLE_LABELS export | Spanish labels for all 3 roles | `role-labels.ts:3–7` — Record<Role, string> with correct values | ✅ COMPLIANT |
| REQ-TMP-08: getRoleLabel helper | Fallback "Usuario" for unknown/undefined | `role-labels.ts:9–12` — `?? "Usuario"` and `if (!role) return "Usuario"` | ✅ COMPLIANT |
| REQ-TMP-09: Authenticated header role badge | Badge visible on all authenticated pages | `_authenticated.tsx:78–80` — `<Badge variant="secondary" className="text-xs">{getRoleLabel(user?.role)}</Badge>` | ✅ COMPLIANT |
| REQ-TMP-10: EditUserDialog 3 options via ROLE_LABELS | admin, template_creator, document_generator options | `EditUserDialog.tsx:128–133` — 3 SelectItems using ROLE_LABELS | ✅ COMPLIANT |
| REQ-TMP-10: Legacy "user" option removed | Prevented client-side | No "user" SelectItem in SelectContent | ✅ COMPLIANT |

**Compliance summary**: 8/8 REQ-TMP-06..10 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Check | Status | Notes |
|-------|--------|-------|
| `permissions.ts` exports `Role` type | ✅ Implemented | Line 1 — union literal type |
| `permissions.ts` exports 4 helpers | ✅ Implemented | Lines 6, 9, 12, 15 |
| Backend-mirror comment in `permissions.ts` | ✅ Implemented | Lines 3–4 |
| `role-labels.ts` exports `ROLE_LABELS` typed `Record<Role, string>` | ✅ Implemented | Lines 3–7 |
| `role-labels.ts` exports `getRoleLabel` with "Usuario" fallback | ✅ Implemented | Lines 9–12 |
| `UploadTemplateDialog` gated with `canUploadTemplates(user?.role)` | ✅ Implemented | `templates/index.tsx:42` |
| Gate is JSX short-circuit (not CSS hide) | ✅ Confirmed | `&&` operator — no `display:none` or `hidden` |
| `EditUserDialog` has exactly 3 role options | ✅ Implemented | Lines 129–131 |
| `EditUserDialog` uses `ROLE_LABELS` for display | ✅ Implemented | `{ROLE_LABELS.admin}` etc. |
| `EditUserDialog` "user" option removed | ✅ Confirmed | Not present in SelectContent |
| Role badge `<Badge variant="secondary" className="text-xs">` | ✅ Implemented | `_authenticated.tsx:78–80` |
| Badge uses `getRoleLabel(user?.role)` | ✅ Implemented | Line 79 |
| `/users` and `/audit` nav tabs admin-only | ✅ Confirmed | Both wrapped `{isAdmin && ...}` at lines 44, 64 |
| `/usage` nav tab not gated | ✅ Confirmed | Pre-existing; intentional (informational page) |
| TypeScript: 0 errors | ✅ Confirmed | `tsc --noEmit` exit 0 |
| Lint: 0 errors, 4 warnings (pre-existing) | ✅ Confirmed | `npm run lint` exit 0 |
| Backend suite: 523 passed, 0 failed | ✅ Confirmed | Zero regressions |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-FE-01: `permissions.ts` exports `Role` type + 4 helpers | ✅ Yes | Exact match; includes `canViewTenantUsage` (exported even if not yet used in nav) |
| ADR-FE-02: `ROLE_LABELS: Record<Role, string>` + fallback helper | ✅ Yes | Spanish labels correct; fallback `"Usuario"` present |
| ADR-FE-02: helper name `roleLabel` | ⚠️ Deviated (cosmetic) | Implemented as `getRoleLabel` instead. Consistent across all usages — no broken contract. Design name was aspirational. |
| ADR-FE-03: `templates/index.tsx` — `{canUploadTemplates(user?.role) && <UploadTemplateDialog />}` | ✅ Yes | Exact pattern at line 42 |
| ADR-FE-03: `_authenticated.tsx` — `<Badge variant="secondary">{roleLabel(user?.role)}</Badge>` | ✅ Yes (name deviated) | `getRoleLabel` used instead of `roleLabel`; `text-xs` class added (not in spec, improves UI) |
| ADR-FE-03: `EditUserDialog` 3 SelectItems + `ROLE_LABELS` display + `?? "document_generator"` fallback | ✅ Yes | Lines 124, 128–133 |
| Phase 5 scope: frontend-only, no backend changes | ✅ Yes | Clean boundary; backend suite unchanged at 523 |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
None.

**SUGGESTION**:
- `getRoleLabel` vs `roleLabel` naming: ADR-FE-02 specifies `roleLabel` as the helper name; apply chose `getRoleLabel`. The naming is a cosmetic deviation — the contract is identical and usage is consistent in all call sites (`_authenticated.tsx:79`). If the team has a preference for one naming convention, it could be aligned in a follow-up. Non-blocking.
- `canViewTenantUsage` is exported from `permissions.ts` but not yet used as a nav guard for the `/usage` route (T-FE-06 confirmed `/usage` is open to all). The helper is correctly defined and available if a future change gates that route. No action needed now.

---

### Test Counts

| Metric | Value |
|--------|-------|
| Backend Phase 4 baseline | 523 |
| After Phase 5 | 523 |
| Net new (Phase 5) | 0 (frontend — no test runner) |
| TypeScript errors | 0 |
| Lint errors | 0 |
| Lint warnings | 4 (pre-existing baseline; no new) |
| Backend failures | 0 |
| Regressions | 0 |

---

### Verdict

**APPROVED**

Phase 5 is complete, correct, and coherent. All 6 frontend tasks implemented following the design. TypeScript exit 0, lint exit 0 (4 pre-existing warnings, 0 new). Backend suite unchanged at 523/523 — zero regressions. REQ-TMP-06 through REQ-TMP-10 are fully satisfied with structural evidence:

- `permissions.ts` mirrors backend with correct 3-role logic + backend reference comment.
- `role-labels.ts` exports correct Spanish labels and `getRoleLabel` fallback helper.
- `UploadTemplateDialog` is conditionally rendered via JSX short-circuit — absent from DOM for `document_generator`.
- `EditUserDialog` shows exactly 3 role options via `ROLE_LABELS`; legacy `"user"` option removed.
- Role badge `<Badge variant="secondary" className="text-xs">` displays `getRoleLabel(user?.role)` in the authenticated header on every page.
- Admin-only nav tabs (`/users`, `/audit`) remain correctly gated with `isAdmin`; `/usage` was and remains intentionally open to all authenticated users.

One cosmetic deviation from design: `getRoleLabel` vs `roleLabel` naming (consistent across all usages, non-blocking).

Phase 6 (T-REG-01, T-REG-02, T-REG-03) may proceed.
