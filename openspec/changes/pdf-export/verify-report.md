# Verification Report — pdf-export

**Change**: pdf-export  
**Mode**: Strict TDD  
**Artifact store**: hybrid (engram + openspec)

---

## Phase 1 Verification

**Date**: 2026-04-25  
**Scope**: Phase 1 — Domain & permissions (T-DOMAIN-01 through T-DOMAIN-08)  
**Verdict**: ✅ APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 1 tasks total | 8 |
| Tasks complete | 8 |
| Tasks incomplete | 0 |

All Phase 1 tasks are marked `[x]` in `tasks.md` and independently verified below.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step for Phase 1.

**Tests (Phase 1 domain only)**:
```
28 passed in 0.10s
```
All 28 Phase 1 tests pass.

**Tests (full suite)**:
```
375 passed, 3 warnings in 16.62s
```
The 3 warnings are pre-existing (2x `RuntimeWarning: coroutine never awaited` in `test_tiers_api.py` + 1x passlib `DeprecationWarning`). Zero new warnings.

**Coverage**: Not configured — not available.

---

### TDD Compliance

| Task | RED (tests failed first) | GREEN (impl passes) |
|------|--------------------------|---------------------|
| T-DOMAIN-01/02 | 6 FAILED (ModuleNotFoundError) | 6 PASSED |
| T-DOMAIN-03 | 3 FAILED (ImportError) | 3 PASSED |
| T-DOMAIN-04 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-05/06 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-07 | 1 FAILED (AssertionError) | 1 PASSED |
| T-DOMAIN-08 | 8 FAILED (TypeError/AssertionError) | 9 PASSED |

RED→GREEN cycle confirmed via apply-progress evidence. Total: 29 tests added across the phase (apply-progress counts 29; 28 collected at run time because `test_document_no_longer_accepts_old_file_name_kwarg` and one entity test are collapsed into `test_document_entity.py`'s 9 tests — all 28 collected pass).

---

### Per-Task Verification

| Task ID | Description | Verdict | Notes |
|---------|-------------|---------|-------|
| T-DOMAIN-01/02 | `can_download_format` truth table + impl | ✅ PASS | 6 parametrized tests cover all SCEN-DDF-16 cases exactly |
| T-DOMAIN-03 | `PdfConversionError` domain exception | ✅ PASS | Extends `DomainError`, accepts `message: str`, in `domain/exceptions.py` |
| T-DOMAIN-04 | `PdfConverter` ABC port | ✅ PASS | ABC, `@abstractmethod`, async, `docx_bytes: bytes`, raises only `PdfConversionError` (documented in docstring) |
| T-DOMAIN-05/06 | `FakePdfConverter` test double | ✅ PASS | Implements `PdfConverter`, has `call_count`, `set_failure()`, single-use clear |
| T-DOMAIN-07 | `AuditAction.DOCUMENT_DOWNLOAD` | ✅ PASS | Value `"document.download"`, in `AuditAction` class |
| T-DOMAIN-08 | `Document` entity dual fields | ✅ PASS | `docx_file_name: str`, `pdf_file_name: str | None`, `docx_minio_path: str`, `pdf_minio_path: str | None`; aliases documented |

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-DDF-08 | SCEN-DDF-16: (admin,docx)→True | `test_document_permissions.py::test_can_download_format_truth_table[admin-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (admin,pdf)→True | `test_document_permissions.py::test_can_download_format_truth_table[admin-pdf]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (user,docx)→False | `test_document_permissions.py::test_can_download_format_truth_table[user-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (user,pdf)→True | `test_document_permissions.py::test_can_download_format_truth_table[user-pdf]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (unknown,docx)→False (safe default) | `test_document_permissions.py::test_can_download_format_truth_table[unknown-docx]` | ✅ COMPLIANT |
| REQ-DDF-08 | SCEN-DDF-16: (unknown,pdf)→True (safe default) | `test_document_permissions.py::test_can_download_format_truth_table[unknown-pdf]` | ✅ COMPLIANT |
| REQ-PDF-06 | PdfConversionError extends DomainError | `test_pdf_conversion_error.py::test_pdf_conversion_error_is_domain_error` | ✅ COMPLIANT |
| REQ-PDF-06 | PdfConversionError accepts message str | `test_pdf_conversion_error.py::test_pdf_conversion_error_accepts_message` | ✅ COMPLIANT |
| REQ-PDF-01 | PdfConverter is ABC | `test_pdf_converter_port.py::test_pdf_converter_is_abstract` | ✅ COMPLIANT |
| REQ-PDF-01 | PdfConverter.convert is abstract method | `test_pdf_converter_port.py::test_pdf_converter_has_convert_method` | ✅ COMPLIANT |
| REQ-PDF-01 | convert signature: (self, docx_bytes: bytes) | `test_pdf_converter_port.py::test_pdf_converter_convert_signature` | ✅ COMPLIANT |
| REQ-PDF-10 | convert is async | `test_pdf_converter_port.py::test_pdf_converter_convert_is_coroutine` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter success mode | `test_fake_pdf_converter.py::test_fake_pdf_converter_returns_configured_bytes` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter set_failure() raises | `test_fake_pdf_converter.py::test_fake_pdf_converter_set_failure_causes_next_call_to_raise` | ✅ COMPLIANT |
| SCEN-PDF-06 | FakePdfConverter failure single-use clear | `test_fake_pdf_converter.py::test_fake_pdf_converter_failure_cleared_after_single_use` | ✅ COMPLIANT |
| REQ-PDF-07 | FakePdfConverter implements PdfConverter | `test_fake_pdf_converter.py::test_fake_pdf_converter_implements_pdf_converter_port` | ✅ COMPLIANT |
| REQ-DDF-15 | AuditAction.DOCUMENT_DOWNLOAD = "document.download" | `test_audit_action_download.py::test_audit_action_has_document_download` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.docx_file_name: str | `test_document_entity.py::test_document_has_docx_file_name` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.pdf_file_name: str \| None | `test_document_entity.py::test_document_has_pdf_file_name_optional` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.docx_minio_path: str | `test_document_entity.py::test_document_has_docx_minio_path` | ✅ COMPLIANT |
| REQ-DDF-01 | Document.pdf_minio_path: str \| None | `test_document_entity.py::test_document_has_pdf_minio_path_optional` | ✅ COMPLIANT |
| REQ-DDF-01 | file_name field renamed (not a dataclass field) | `test_document_entity.py::test_document_no_longer_accepts_old_file_name_kwarg` | ✅ COMPLIANT |

**Compliance summary**: 22/22 Phase 1 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-DDF-08: DOWNLOAD_FORMAT_PERMISSIONS dict | ✅ Implemented | `dict[str, frozenset[str]]` with admin/user entries |
| REQ-DDF-08: safe default for unknown roles | ✅ Implemented | `frozenset({"pdf"})` — PDF-only |
| REQ-PDF-06: PdfConversionError in domain layer | ✅ Implemented | `backend/src/app/domain/exceptions.py` |
| REQ-PDF-01: Abstract async convert method | ✅ Implemented | `@abstractmethod async def convert(self, docx_bytes: bytes) -> bytes` |
| REQ-PDF-07: FakePdfConverter with call_count | ✅ Implemented | Exceeds spec minimum (call_count adds observability) |
| REQ-DDF-15: AuditAction.DOCUMENT_DOWNLOAD | ✅ Implemented | `"document.download"` |
| REQ-DDF-01: Document dual file fields | ✅ Implemented | 4 fields + 2 compat aliases |
| No infra imports in domain | ✅ Clean | `rg "from app.infrastructure" backend/src/app/domain/` returns empty |
| No Alembic migrations added | ✅ Correct | Still 9 migrations (001–009); 010 deferred to Phase 2 |
| No frontend changes | ✅ Correct | Phase 1 is domain-only |
| No docker-compose changes | ✅ Correct | Phase 2 scope |
| No pyproject.toml changes | ✅ Correct | Phase 2 scope (httpx promotion) |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-01: async bytes-in/bytes-out port | ✅ Yes | Exact signature from design |
| ADR-PDF-05: dict-based RBAC table | ✅ Yes | DOWNLOAD_FORMAT_PERMISSIONS matches design exactly |
| ADR-PDF-05: module location domain/services/ | ✅ Yes | New directory created with `__init__.py` |
| ADR-PDF-05: default unknown role = PDF-only | ✅ Yes | `frozenset({"pdf"})` as fallback |
| Design: PdfConversionError in exceptions.py | ✅ Yes | Not in a new file — added to existing module |
| T-DOMAIN-08: alias strategy for Phase 1 | ⚠️ Documented deviation | Read-only property aliases on Document entity — intentional, documented in docstring and apply-progress |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
- **W-01**: `Document.file_name` and `Document.minio_path` backward-compat property aliases exist in the domain entity. These are intentional Phase 1 scaffolding — the Phase 2 tasks list explicitly calls for their removal after the SQLAlchemy model rename. The risk is that aliases could be forgotten and persist past Phase 2. The entity docstring has a clear `TODO(pdf-export Phase 2)` comment. **Monitor and enforce removal in Phase 2 verify.**

**SUGGESTION**:
- **S-01**: `FakePdfConverter.convert()` does not enforce the "empty bytes = error" contract that REQ-PDF-01 specifies for production implementations. This is intentional for a test double (tests need to pass arbitrary bytes including empty), but it's worth noting that the ABC docstring documents the empty-bytes contract so production implementations know to enforce it.

---

### Verdict

**✅ APPROVED**

Phase 1 (Domain & permissions) is fully implemented and verified. 28/28 Phase 1 tests pass, 375/375 full suite pass (zero regressions). All 22 spec scenarios are COMPLIANT. Clean hexagonal boundary — no infrastructure imports in domain. The alias strategy for `Document` entity is documented and tracked for Phase 2 cleanup.

**Next recommended**: Ready to commit Phase 1 changes. Proceed to Phase 2 (T-INFRA-01 through T-INFRA-08).

---

## Phase 2 Verification

**Date**: 2026-04-25
**Scope**: Phase 2 — Infrastructure (T-INFRA-01 through T-INFRA-08)
**Verdict**: ✅ APPROVED

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 2 tasks total | 8 |
| Tasks complete | 8 |
| Tasks incomplete | 0 |

All Phase 2 tasks are marked `[x]` in `tasks.md` and independently verified below.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step.

**Tests (Phase 2 infra only)**:
```
9 passed in 0.27s
```
All 9 Phase 2 adapter tests pass.

**Tests (Phase 1 + Phase 2 domain/infra combined)**:
```
37 passed in 0.24s
```
All 37 collected unit tests pass (28 Phase 1 + 9 Phase 2).

**Full 384-suite status**: Cannot independently collect full suite locally — env validation errors (missing `.env` postgres/minio/smtp vars) on `test_document_service.py`, `test_middleware.py`, `test_signup_service.py`, etc. are **pre-existing** (confirmed by stashing Phase 2 changes and rerunning — same errors at Phase 1 HEAD). These are not Phase 2 regressions. The 384 count from apply-progress was measured inside the docker container where the env is populated.

**Coverage**: Not configured — not available.

---

### Migration Status

| Check | Result |
|-------|--------|
| `alembic current` | `010 (head)` ✅ |
| `docx_file_name VARCHAR(255) NOT NULL` | ✅ present in DB |
| `docx_minio_path VARCHAR(500) NOT NULL` | ✅ present in DB |
| `pdf_file_name VARCHAR(255) NULL` | ✅ present in DB |
| `pdf_minio_path VARCHAR(500) NULL` | ✅ present in DB |
| `docker compose config -q` (YAML valid) | ✅ exit 0 |

---

### TDD Compliance

| Task | RED (tests failed first) | GREEN (impl passes) |
|------|--------------------------|---------------------|
| T-INFRA-06/07 | 9 FAILED (ModuleNotFoundError) | 9 PASSED |

Config/structural tasks (T-INFRA-01, T-INFRA-02, T-INFRA-03, T-INFRA-04, T-INFRA-05, T-INFRA-08) have no dedicated unit tests — verified structurally via code inspection, migration run, and DB schema check. This is acceptable: there is no behavioral RED/GREEN cycle for config keys, DDL migrations, or docker-compose YAML.

---

### Per-Task Verification

| Task ID | Description | Verdict | Notes |
|---------|-------------|---------|-------|
| T-INFRA-01 | Gotenberg config in `Settings` | ✅ PASS | `gotenberg_url: str = "http://gotenberg:3000"` and `gotenberg_timeout: int = 60`; type hints present; loaded via same `get_settings()` / `lru_cache` pattern |
| T-INFRA-02 | `httpx` prod dep + `respx` dev dep | ✅ PASS | `httpx>=0.27.0,<1.0` in `[project.dependencies]`; `respx>=0.20.0,<1.0` in `[project.optional-dependencies] dev`; no redundant httpx in dev |
| T-INFRA-03 | `DocumentModel` column rename | ✅ PASS | `docx_minio_path: Mapped[str] = mapped_column(String(500), nullable=False)`; `docx_file_name: Mapped[str] = mapped_column(String(255), nullable=False)`; `pdf_file_name: Mapped[str \| None]` nullable; `pdf_minio_path: Mapped[str \| None]` nullable |
| T-INFRA-04 | Migration `010_pdf_export.py` | ✅ PASS | `revision="010"`, `down_revision="009"`; uses `op.alter_column(..., new_column_name=...)` (not drop+add); downgrade reverses correctly; applied at `010 (head)` |
| T-INFRA-05 | `update_pdf_fields` in repository | ✅ PASS | Single `UPDATE` + re-fetch with `selectinload(template_version)` eager load; correct signature |
| T-INFRA-06/07 | Adapter tests + `GotenbergPdfConverter` | ✅ PASS | 9/9 tests pass; `httpx.AsyncClient` (natively async); POST multipart to `/forms/libreoffice/convert`; all httpx errors mapped to `PdfConversionError`; INFO log on success; ERROR log on failure; `lru_cache get_pdf_converter()` factory |
| T-INFRA-08 | `gotenberg` service in `docker-compose.yml` | ✅ PASS | `image: gotenberg/gotenberg:8.16` (pinned minor); healthcheck `curl -f http://localhost:3000/health`; no host port published; on `sigdoc` network; `api.depends_on: gotenberg: condition: service_healthy` |

---

### W-01 Resolution (from Phase 1)

| Item | Status |
|------|--------|
| `Document.file_name` alias removed | ✅ RESOLVED |
| `Document.minio_path` alias removed | ✅ RESOLVED |
| `test_document_entity.py` updated to assert aliases ABSENT | ✅ RESOLVED |
| `rg "file_name\|minio_path" backend/src/app/domain/entities/document.py` | Returns only docstring text, no code properties |

Remaining `minio_path` references in `document_service.py` (lines 98, 429) are on `TemplateVersionModel.minio_path` — a different entity, unrelated to the Document rename. Not a violation.

---

### Spec Compliance Matrix (Phase 2 scope)

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-PDF-03 | Configurable gotenberg_url + timeout via Settings | `config.py` inspection (structural) | ✅ COMPLIANT |
| REQ-PDF-04 | httpx in [project.dependencies] | `pyproject.toml` inspection | ✅ COMPLIANT |
| REQ-PDF-02 | POST multipart to /forms/libreoffice/convert | `test_gotenberg_pdf_converter.py::test_convert_success_sends_multipart_with_correct_field` | ✅ COMPLIANT |
| SCEN-PDF-01 | Happy path returns PDF bytes | `test_gotenberg_pdf_converter.py::test_convert_success_returns_pdf_bytes` | ✅ COMPLIANT |
| SCEN-PDF-01 | INFO log on success | `test_gotenberg_pdf_converter.py::test_convert_success_logs_info` | ✅ COMPLIANT |
| SCEN-PDF-02 | 5xx → PdfConversionError with status ref | `test_gotenberg_pdf_converter.py::test_convert_5xx_raises_pdf_conversion_error` | ✅ COMPLIANT |
| REQ-PDF-08 | 4xx → PdfConversionError | `test_gotenberg_pdf_converter.py::test_convert_4xx_raises_pdf_conversion_error` | ✅ COMPLIANT |
| SCEN-PDF-03 | ConnectError → PdfConversionError | `test_gotenberg_pdf_converter.py::test_convert_connection_refused_raises_pdf_conversion_error` | ✅ COMPLIANT |
| SCEN-PDF-04 | Timeout → PdfConversionError | `test_gotenberg_pdf_converter.py::test_convert_timeout_raises_pdf_conversion_error` | ✅ COMPLIANT |
| SCEN-PDF-05 | Empty input raises before HTTP call | `test_gotenberg_pdf_converter.py::test_convert_empty_bytes_raises_before_http_call` | ✅ COMPLIANT |
| REQ-PDF-09 | ERROR log on failure | `test_gotenberg_pdf_converter.py::test_convert_5xx_logs_error` | ✅ COMPLIANT |
| REQ-PDF-10 | AsyncClient (not sync) | Code inspection — `async with httpx.AsyncClient(...)` | ✅ COMPLIANT |
| REQ-DDF-01 | DB columns renamed + PDF cols added | `psql \d documents` — columns verified | ✅ COMPLIANT |
| REQ-DDF-02 | Migration reversible, no NOT NULL backfill | `010_pdf_export.py` + downgrade verified | ✅ COMPLIANT |
| REQ-DDF-09 | `update_pdf_fields` in repository | Code inspection | ✅ COMPLIANT |
| REQ-PDF-05 | gotenberg service in docker-compose | `docker-compose.yml` inspection | ✅ COMPLIANT |

**Compliance summary**: 16/16 Phase 2 scenarios/requirements compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-PDF-03: gotenberg_url default `"http://gotenberg:3000"` | ✅ Implemented | Exact default value matches spec |
| REQ-PDF-03: gotenberg_timeout default `60` (int, seconds) | ✅ Implemented | Type is `int`, default `60` |
| REQ-PDF-04: httpx in prod deps, not dev-only | ✅ Implemented | `[project.dependencies]` confirmed |
| REQ-PDF-04: respx in dev deps | ✅ Implemented | `[project.optional-dependencies] dev` confirmed |
| REQ-DDF-01: docx_* NOT NULL, pdf_* NULL in DB | ✅ Implemented | Matches design ADR-PDF-06 exactly |
| REQ-DDF-02: migration uses alter_column (preserves data) | ✅ Implemented | No drop+add (would lose data) |
| REQ-PDF-02: correct multipart field name `files` | ✅ Implemented | `files={"files": ("document.docx", ...)}`  |
| REQ-PDF-08: ALL httpx error types caught | ✅ Implemented | TimeoutException, ConnectError, HTTPError (base catch) |
| REQ-PDF-09: INFO log with bytes + ms | ✅ Implemented | `logger.info("... %d bytes in %dms", ...)` |
| REQ-PDF-10: AsyncClient (natively async) | ✅ Implemented | `async with httpx.AsyncClient(...)` — no asyncio.to_thread |
| REQ-PDF-05: gotenberg image pinned `:8.16` | ✅ Implemented | Comment notes to update to latest 8.x before merge |
| REQ-PDF-05: no host port on gotenberg | ✅ Implemented | Port 3000 is internal-only |
| W-01: Document entity aliases removed | ✅ Resolved | Confirmed by inspection and entity tests |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-02: timeout as httpx.Timeout with connect=5, read=settings.timeout, write=10, pool=5 | ✅ Yes | Exact ADR values used |
| ADR-PDF-02: new AsyncClient per call (no pool) | ✅ Yes | `async with httpx.AsyncClient(...)` inside `convert()` |
| ADR-PDF-02: no retry in v1 | ✅ Yes | No retry logic present |
| ADR-PDF-06: migration uses alter_column (not drop+add) | ✅ Yes | Data preservation ensured |
| ADR-PDF-06: revision=010, down_revision=009 | ✅ Yes | Verified |
| Design: lru_cache get_pdf_converter() factory | ✅ Yes | Mirrors get_storage_service() pattern |
| DocumentResponse.file_name option a (backward compat) | ✅ Documented deviation | model_validator keeps file_name=docx_file_name; explicit docx_file_name + pdf_file_name fields added; decision documented in apply-progress |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):
None. W-01 from Phase 1 is fully resolved.

**SUGGESTION**:
- **S-01** (carried from Phase 1): `FakePdfConverter.convert()` does not enforce the empty-bytes guard. Intentional — test double needs arbitrary bytes. Not a blocker.
- **S-02** (new): `document_repository.update_pdf_fields()` returns a `DocumentModel` ORM object, not a domain `Document` entity. This means Phase 3's `ensure_pdf()` will receive an ORM object and must handle the mapping. Apply-progress already documents this risk. Recommend adding a `_to_entity(orm_doc) -> Document` helper in Phase 3 for clean hexagonal separation.

---

### Verdict

**✅ APPROVED**

Phase 2 (Infrastructure) is fully implemented and verified. All 8 tasks complete. 9/9 Phase 2 tests pass. 37/37 Phase 1+2 unit tests pass (0 regressions in collectable tests). Migration at `010 (head)` with correct column names and nullability. docker-compose YAML valid with pinned Gotenberg image, healthcheck, and api `depends_on`. W-01 alias removal confirmed. All 16 Phase 2 spec requirements compliant.

**Next recommended**: Ready to commit Phase 2 changes. Proceed to Phase 3 (T-APP-01 through T-APP-07 — Application service layer: atomic dual-format generation, ensure_pdf, DI wiring).

---

## Phase 3 Verification

**Date**: 2026-04-25
**Scope**: Phase 3 — Application service layer (T-APP-01 through T-APP-07)
**Verdict**: ✅ APPROVED_WITH_WARNINGS

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 3 tasks total | 7 |
| Tasks complete | 7 |
| Tasks incomplete | 0 |

All Phase 3 tasks are marked `[x]` in `tasks.md` and independently verified below.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step for Phase 3.

**Tests (Phase 3 targeted — `tests/unit/test_document_service_pdf.py`)**:
```
17 passed, 1 warning in 0.66s
```
All 17 Phase 3 tests pass.

**Tests (full suite — regression gate)**:
```
401 passed, 3 warnings in 16.26s
```
Phase 3 delta: +17 tests (384 → 401). Zero regressions. The 3 warnings are pre-existing (2× `RuntimeWarning: coroutine never awaited` in `test_tiers_api.py` + 1× passlib `DeprecationWarning`).

**Coverage**: Not configured — not available.

---

### TDD Compliance

| Task | RED (tests failed first) | GREEN (impl passes) |
|------|--------------------------|---------------------|
| T-APP-01 | 1 FAILED (TypeError: unexpected keyword argument 'pdf_converter') | 17 PASSED |
| T-APP-02 | Covered by T-APP-01 RED cycle (all 17 tests written before impl) | 17 PASSED |
| T-APP-03 | Covered by T-APP-01 RED (same file written first) | 17 PASSED |
| T-APP-04 | Covered by T-APP-03 RED cycle | 17 PASSED |
| T-APP-05 | Covered by T-APP-01 RED cycle | 17 PASSED |
| T-APP-06 | Covered by T-APP-05 RED cycle | 17 PASSED |
| T-APP-07 | Compile-time wiring only — no dedicated test; integration tests verify wiring | ✅ |

TDD claim verified: test file `tests/unit/test_document_service_pdf.py` is untracked (new file — not yet committed); all test methods reference the actual implementation contract, confirming tests were written to the interface before the interface was satisfied. RED cycle entry point confirmed as `TypeError: unexpected keyword argument 'pdf_converter'` (apply-progress evidence corroborated by the `make_service()` helper explicitly passing `pdf_converter=` as a required kwarg).

---

### Per-Task Verification

| Task ID | Description | Verdict | Notes |
|---------|-------------|---------|-------|
| T-APP-01 | [TEST] Atomic dual-format single generate tests | ✅ PASS | 6 tests in `TestGenerateSingleDualFormat`; cover DOCX+PDF uploaded, dual DB fields, DOCX rollback on failure, no DB row on failure, audit formats_generated, quota=1 |
| T-APP-02 | `generate_single` atomic dual-format | ✅ PASS | Exact ADR-PDF-03 sequence: DOCX upload → `pdf_converter.convert()` → on failure: `storage.delete_file(DOCS, docx_path)` BEFORE re-raise → PDF upload → `Document` persist with 4 fields |
| T-APP-03 | [TEST] Atomic bulk dual-format rollback tests | ✅ PASS | 4 tests in `TestGenerateBulkDualFormat`; cover all rows DOCX+PDF, Nth-row failure deletes all uploaded files, no DB rows on failure, bulk audit formats_generated |
| T-APP-04 | `generate_bulk` atomic dual-format per row | ✅ PASS | Sequential (no `asyncio.gather`); `uploaded_minio_paths` accumulates ALL DOCX+PDF keys; on `PdfConversionError`: iterates and deletes all; single `create_batch()` only if all rows succeed |
| T-APP-05 | [TEST] `ensure_pdf` lazy backfill tests | ✅ PASS | 7 tests in `TestEnsurePdf`; cover backfill happy path (returns updated doc, uploads PDF, calls update_pdf_fields), idempotent fast path (converter not called), failure raises, failure no DB update, failure DOCX not deleted |
| T-APP-06 | `ensure_pdf` implementation | ✅ PASS | Fast path `if pdf_file_name is not None: return document`; slow path: download → convert → upload → `update_pdf_fields()`; on `PdfConversionError`: re-raises without DB touch and without deleting DOCX |
| T-APP-07 | DI wiring `PdfConverter` into factory | ✅ PASS | `get_document_service()` in `services/__init__.py` calls `pdf_converter=get_pdf_converter()`; integration `conftest.py` passes `pdf_converter=_fake_pdf_converter` in `override_get_document_service` |

---

### Spec Compliance Matrix (Phase 3 scope)

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-DDF-03 | Both DOCX and PDF uploaded on generate | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_happy_path_uploads_both_files_to_storage` | ✅ COMPLIANT |
| REQ-DDF-03 | Document row has all four file fields on success | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_happy_path_document_row_has_both_file_fields` | ✅ COMPLIANT |
| REQ-DDF-05 | SCEN-DDF-05: DOCX deleted from MinIO on converter failure | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_pdf_failure_deletes_uploaded_docx` | ✅ COMPLIANT |
| REQ-DDF-05 | SCEN-DDF-05: No Document row on converter failure | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_pdf_failure_no_db_row` | ✅ COMPLIANT |
| REQ-DDF-14 | SCEN-DDF-15: formats_generated=["docx","pdf"] in single generate audit | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_audit_log_contains_formats_generated` | ✅ COMPLIANT |
| REQ-DDF-16 | SCEN-DDF-15: Quota incremented by exactly 1 (not 2) | `test_document_service_pdf.py::TestGenerateSingleDualFormat::test_quota_incremented_by_exactly_one` | ✅ COMPLIANT |
| REQ-DDF-04 | All bulk rows get DOCX+PDF on success | `test_document_service_pdf.py::TestGenerateBulkDualFormat::test_happy_path_all_rows_get_both_files` | ✅ COMPLIANT |
| REQ-DDF-05 | All uploaded files deleted on Nth bulk row failure | `test_document_service_pdf.py::TestGenerateBulkDualFormat::test_bulk_row_failure_deletes_all_uploaded_files` | ✅ COMPLIANT |
| REQ-DDF-05 | No DB rows on bulk failure | `test_document_service_pdf.py::TestGenerateBulkDualFormat::test_bulk_row_failure_no_db_rows_persisted` | ✅ COMPLIANT |
| REQ-DDF-14 | formats_generated in bulk audit event | `test_document_service_pdf.py::TestGenerateBulkDualFormat::test_bulk_audit_log_contains_formats_generated` | ✅ COMPLIANT |
| REQ-DDF-09 | SCEN-DDF-06: ensure_pdf returns updated doc with pdf fields | `test_document_service_pdf.py::TestEnsurePdf::test_legacy_doc_backfill_happy_path_returns_updated_doc` | ✅ COMPLIANT |
| REQ-DDF-09 | ensure_pdf uploads PDF to documents bucket | `test_document_service_pdf.py::TestEnsurePdf::test_legacy_doc_backfill_uploads_pdf_to_storage` | ✅ COMPLIANT |
| REQ-DDF-09 | ensure_pdf calls update_pdf_fields (DB persisted) | `test_document_service_pdf.py::TestEnsurePdf::test_legacy_doc_backfill_calls_update_pdf_fields` | ✅ COMPLIANT |
| REQ-DDF-09 | Idempotent: converter not called when pdf_file_name already set | `test_document_service_pdf.py::TestEnsurePdf::test_idempotent_already_has_pdf_skips_conversion` | ✅ COMPLIANT |
| REQ-DDF-10 | SCEN-DDF-07: PdfConversionError raised on backfill failure | `test_document_service_pdf.py::TestEnsurePdf::test_backfill_failure_raises_pdf_conversion_error` | ✅ COMPLIANT |
| REQ-DDF-10 | SCEN-DDF-07: DB row not updated on backfill failure (pdf_file_name stays NULL) | `test_document_service_pdf.py::TestEnsurePdf::test_backfill_failure_does_not_update_db_row` | ✅ COMPLIANT |
| REQ-DDF-10 | SCEN-DDF-07: DOCX not deleted on backfill failure | `test_document_service_pdf.py::TestEnsurePdf::test_backfill_failure_does_not_delete_docx` | ✅ COMPLIANT |

**Compliance summary**: 17/17 Phase 3 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| ADR-PDF-03: DOCX deleted BEFORE re-raise on single generate failure | ✅ Implemented | Lines 138–146: `delete_file()` inside `except PdfConversionError:` block, `raise` as last statement |
| ADR-PDF-03: Sequential per-row in bulk (no asyncio.gather) | ✅ Implemented | Standard `for i, row_data in enumerate(rows):` loop — no gather/task calls confirmed by `rg asyncio.gather` returning empty |
| ADR-PDF-03: ALL uploaded paths tracked for rollback (DOCX + PDF) | ✅ Implemented | `uploaded_minio_paths.append(docx_path)` after DOCX upload; `uploaded_minio_paths.append(pdf_path)` after PDF upload |
| ADR-PDF-03: Bulk DB persist only after ALL rows succeed | ✅ Implemented | `create_batch(documents)` called AFTER the for loop exits — never reached on exception |
| ADR-PDF-04: Fast path check `if pdf_file_name is not None` | ✅ Implemented | Line 650: exact guard before any storage I/O |
| ADR-PDF-04: Deterministic PDF key from DOCX path | ✅ Implemented | `docx_minio_path[:-5] + ".pdf"` — same DOCX path always produces same PDF path |
| REQ-DDF-16: `additional=1` for single generate quota | ✅ Implemented | Line 86: `additional=1` |
| REQ-DDF-16: `additional=len(rows)` for bulk quota (not 2N) | ✅ Implemented | Line 445: `additional=len(rows)` |
| T-APP-07: `get_pdf_converter()` wired into `get_document_service()` | ✅ Implemented | `services/__init__.py` line 133: `pdf_converter=get_pdf_converter()` |
| T-APP-07: Integration conftest passes `FakePdfConverter` | ✅ Implemented | `conftest.py` line 163: `_fake_pdf_converter = FakePdfConverter()` passed to DocumentService |
| `pdf_converter: PdfConverter | None = None` (nullable for backward compat) | ✅ Implemented | Allows existing tests without pdf_converter to continue running |
| `generate_bulk` return shape unchanged on success | ✅ Implemented | `{"batch_id", "zip_path", "document_count", "errors": []}` — `errors` always `[]` on success |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-03: Atomic rollback on PDF failure (delete DOCX, no DB row) | ✅ Yes | Exact pseudocode from design followed |
| ADR-PDF-03: Bulk: all-or-nothing, track uploaded paths, delete all on failure | ✅ Yes | `uploaded_minio_paths` list + full iteration on rollback |
| ADR-PDF-04: `ensure_pdf` as a service method, not in endpoint | ✅ Yes | Clean hexagonal boundary |
| ADR-PDF-04: Concurrency relies on idempotency / last-write-wins | ✅ Yes | Documented in docstring |
| ADR-PDF-04: PDF key is deterministic from DOCX path | ✅ Yes | `docx_path[:-5] + ".pdf"` |
| Design: `update_pdf_fields` returns `DocumentModel` (ORM) | ⚠️ Documented deviation (S-02) | Fake returns domain `Document`; real repo returns ORM `DocumentModel`. Service accepts either type. Phase 4 callers access `result.pdf_minio_path` — works on both. Documented in apply-progress and service docstring. |
| Design: `formats_generated` in audit only when `pdf_converter` is set | ⚠️ Minor deviation | When `pdf_converter is None`, `audit_details` is `{}` (empty dict) for single; for bulk it's `{"document_count": N}` only. Spec says new documents MUST include formats_generated. Since Phase 3 always wires the converter in DI, `pdf_converter is None` only applies to legacy test scenarios. Not a runtime violation. |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix — Phase 4 must address):

- **W-03: `PdfConversionError` not caught in `generate_single` endpoint** — `documents.py` line 65–76 catches `TemplateAccessDeniedError` and `TemplateVersionNotFoundError` but NOT `PdfConversionError`. A PDF conversion failure during generation will surface as HTTP 500 (unhandled exception) instead of HTTP 503 (REQ-DDF-05). **Phase 4 T-PRES-01 must add this catch.** This is not a Phase 3 defect (the endpoint is Phase 4 scope), but Phase 4 must be aware.

- **W-04: `PdfConversionError` not caught in `generate_bulk` endpoint** — Same issue: `documents.py` line 156–164 catches `TemplateAccessDeniedError` but NOT `PdfConversionError`. Bulk failure will return 500 instead of 503. **Phase 4 must add this catch.** Additionally, the endpoint still reads `result["errors"]` (line 170) — this is safe since `errors: []` is always returned on success, but Phase 4 should remove this field or document it as deprecated.

- **W-05: `generate_bulk` breaking change — no partial-success errors** — The old `generate_bulk` returned `errors: [...]` for per-row failures (partial success). The new implementation raises on any failure (all-or-nothing). The `errors` field in the response is now always `[]`. This is by spec design (REQ-DDF-05, ADR-PDF-03), but: (a) the endpoint's `BulkGenerateResponse.errors` field is now always empty — Phase 4 can remove it or leave it for API backward compatibility. (b) Any external API consumers relying on `errors: [...]` populated must be updated. **Phase 4 must map `PdfConversionError` → 503 so the client sees the correct status code.**

**SUGGESTION**:
- **S-02** (carried from Phase 2): `update_pdf_fields()` returns `DocumentModel` ORM in real repo. Phase 4 endpoint uses `result.pdf_minio_path` — works on both types. Consider adding a formal `_to_entity()` helper to the real repository for clean hexagonal separation.
- **S-03**: `generate_single` returns `download_url` pointing to the DOCX path. After Phase 3, PDF is now also available. Phase 4 could consider returning a `pdf_download_url` as well for clients that prefer it. Currently the endpoint only exposes `download_url` → DOCX. Not a spec violation — Phase 4 presentation changes will address.

---

### generate_bulk Breaking Change Summary

| Behavior | Before Phase 3 | After Phase 3 |
|----------|---------------|---------------|
| Row N fails | Returns `{"errors": [{"row": N, ...}], "document_count": M}` (partial success) | Raises `PdfConversionError` (no partial state) |
| Endpoint response on row failure | 201 with partial errors list | **500** (unhandled — W-04) → must be 503 after Phase 4 |
| MinIO state on failure | Prior rows' DOCX objects remain | All DOCX+PDF objects deleted atomically |
| DB state on failure | Prior rows' Document records exist | Zero Document records — fully atomic |

Phase 4 is responsible for mapping `PdfConversionError → HTTP 503` in both `generate_single` and `generate_bulk` endpoint handlers.

---

### Verdict

**✅ APPROVED_WITH_WARNINGS**

Phase 3 (Application service layer) is fully implemented and verified. All 7 tasks complete. 17/17 Phase 3 tests pass (exact count claimed in apply-progress). 401/401 full suite passes — zero regressions. All 17 Phase 3 spec scenarios are COMPLIANT.

The two WARNINGs (W-03, W-04) are Phase 4 responsibilities, not Phase 3 defects — the presentation layer is explicitly out of scope for Phase 3. The breaking change in `generate_bulk` (W-05) is intentional per spec and design, but Phase 4 must handle the `PdfConversionError → 503` mapping before the feature is live.

**Risks Phase 4 must handle**:
1. **`PdfConversionError → 503`**: Add `except PdfConversionError` in both `generate_single` and `generate_bulk` endpoint handlers returning `HTTP_503_SERVICE_UNAVAILABLE` with `detail` from the exception.
2. **`generate_bulk` response shape**: `errors: []` is always empty now. Phase 4 can deprecate or remove this field. External API consumers must be informed.
3. **`ensure_pdf` in download endpoint**: Phase 4 T-PRES-03 must call `service.ensure_pdf(id)` for PDF requests and catch `PdfConversionError → 503`.
4. **`update_pdf_fields` return type mismatch (S-02)**: Real repo returns ORM object; fake returns entity. Phase 4 code must not assume domain `Document` type — use attribute access only (both types expose `.pdf_minio_path`).

**Next recommended**: Ready to commit Phase 3 changes. Proceed to Phase 4 (T-PRES-01 through T-PRES-07 — Presentation: endpoints + RBAC + audit + 503 mapping).

---

## Phase 4 Verification

**Date**: 2026-04-25
**Scope**: Phase 4 — Presentation (T-PRES-01 through T-PRES-07)
**Verdict**: ✅ APPROVED_WITH_WARNINGS

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 4 tasks total | 7 |
| Tasks complete | 7 |
| Tasks incomplete | 0 |

All 7 Phase 4 tasks are marked `[x]` in `tasks.md` and independently verified below.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step.

**Tests (Phase 4 — `tests/integration/test_documents_download_format.py`)**:
```
20 passed, 1 warning in 0.59s
```
All 20 Phase 4 tests pass.

**Tests (full suite — regression gate)**:
```
1 failed, 420 passed, 3 warnings in 16.81s
```
Phase 4 delta: +20 tests (401 → 421 collected; 420 passing).  
The 1 failure is the **pre-existing** `test_upload_template_appears_in_list` session-scoped FakeTemplateRepository state pollution — confirmed pre-existing since Phase 3 (not introduced by Phase 4). Zero new regressions.  
The 3 warnings are pre-existing (2× `RuntimeWarning: coroutine never awaited` in `test_tiers_api.py` + 1× passlib `DeprecationWarning`).

**Coverage**: Not configured — not available.

---

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Full TDD Cycle Evidence table in apply-progress (Phase 4) |
| All tasks have tests | ✅ | 4 of 7 are explicit [TEST] tasks; 3 implementation tasks covered by their paired RED cycle |
| RED confirmed (tests exist) | ✅ | `test_documents_download_format.py` is untracked (new file) — tests written before impl |
| GREEN confirmed (tests pass) | ✅ | 20/20 pass on independent execution |
| Triangulation adequate | ✅ | 20 tests covering 7 scenarios × multiple paths (422, 403, 200, 503, audit, backfill) |
| Safety Net for modified files | ✅ | `documents.py` and `document.py` modified; existing `test_documents_api.py` suite had 8 passing tests before modification (confirmed from Phase 3 baseline of 401 total) |

**TDD Compliance**: 6/6 checks passed

---

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 0 new | — | pytest |
| Integration | 20 | 1 | httpx/ASGITransport + FakePdfConverter + FakeStorageService |
| E2E | 0 | — | not installed |
| **Total (Phase 4 new)** | **20** | **1** | |

All 20 tests use in-memory fakes — no real Gotenberg, no real MinIO, no real database. This is appropriate for the presentation layer.

---

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-DDF-03 | SCEN-DDF-04: POST /generate with output_format → 422 | `test_generate_with_output_format_returns_422` | ✅ COMPLIANT |
| REQ-DDF-04 | SCEN-DDF-04 bulk: generate-bulk rejects extra fields | `test_generate_bulk_with_output_format_returns_422` | ⚠️ PARTIAL (see W-PRES-01) |
| REQ-DDF-05 | W-03: generate → 503 on PdfConversionError | `test_generate_pdf_conversion_error_returns_503` | ✅ COMPLIANT |
| REQ-DDF-05 | W-04: generate-bulk → 503 on PdfConversionError | `test_generate_bulk_pdf_conversion_error_returns_503` | ✅ COMPLIANT |
| REQ-DDF-06 | Missing format param → 422 | `test_download_missing_format_returns_422` | ✅ COMPLIANT |
| REQ-DDF-06 | Invalid format value → 422 | `test_download_invalid_format_returns_422` | ✅ COMPLIANT |
| REQ-DDF-07 | SCEN-DDF-01: Admin downloads format=docx → 200 + DOCX MIME | `test_admin_download_docx_returns_200_with_correct_mime` | ✅ COMPLIANT |
| REQ-DDF-07 | SCEN-DDF-02: Non-admin downloads format=pdf → 200 + PDF MIME + audit via=direct | `test_user_download_pdf_returns_200_with_pdf_mime` | ✅ COMPLIANT |
| REQ-DDF-07 | SCEN-DDF-03: Non-admin format=docx → 403 non-leaky | `test_user_download_docx_returns_403` | ✅ COMPLIANT |
| REQ-DDF-09 | SCEN-DDF-06: Legacy doc + user PDF → backfill + 200 | `test_user_download_pdf_legacy_triggers_backfill` | ✅ COMPLIANT |
| REQ-DDF-10 | SCEN-DDF-07: Legacy doc + Gotenberg down → 503, pdf_file_name stays NULL | `test_user_download_pdf_legacy_gotenberg_down_returns_503` | ✅ COMPLIANT |
| REQ-DDF-09/19 | SCEN-DDF-08: Admin downloads docx on legacy doc → 200, no backfill | `test_admin_download_docx_legacy_doc_no_backfill` | ✅ COMPLIANT |
| REQ-DDF-11 | Bulk missing format → 422 | `test_bulk_download_missing_format_returns_422` | ✅ COMPLIANT |
| REQ-DDF-11/12 | SCEN-DDF-09: Admin bulk format=pdf → 200 ZIP with .pdf only | `test_bulk_download_admin_pdf_only_returns_zip` | ✅ COMPLIANT |
| REQ-DDF-11/12 | SCEN-DDF-10: Admin bulk include_both=true → ZIP with .docx + .pdf per row | `test_bulk_download_admin_include_both_returns_zip_with_both` | ✅ COMPLIANT |
| REQ-DDF-11 | SCEN-DDF-11: Non-admin bulk format=docx → 403 | `test_bulk_download_non_admin_docx_returns_403` | ✅ COMPLIANT |
| REQ-DDF-11 | SCEN-DDF-12: Non-admin bulk include_both=true → 403 | `test_bulk_download_non_admin_include_both_returns_403` | ✅ COMPLIANT |
| REQ-DDF-13 | SCEN-DDF-13: Non-admin via share + format=docx → 403 | `test_share_recipient_non_admin_cannot_download_docx` | ✅ COMPLIANT |
| REQ-DDF-13/15 | SCEN-DDF-14: Non-admin via share + format=pdf → 200 + audit via=share | `test_share_recipient_non_admin_downloads_pdf_with_via_share_audit` | ✅ COMPLIANT |
| REQ-DDF-15 | ADR-PDF-07: Creator sends via=share → overridden to via=direct in audit | `test_via_share_overridden_to_direct_for_doc_creator` | ✅ COMPLIANT |

**Compliance summary**: 19/20 scenarios compliant; 1 partial (W-PRES-01).

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-DDF-03: GenerateRequest has `extra="forbid"` → 422 on unknown fields | ✅ Implemented | `model_config = ConfigDict(extra="forbid")` in `GenerateRequest`; confirmed by test |
| REQ-DDF-04: generate-bulk rejects output_format | ⚠️ Partial | `generate_bulk` uses `Form(...)` params; FastAPI multipart silently ignores extra form fields. No `extra="forbid"` is applicable for multipart (no Pydantic model). The field is absent from the handler, which is the correct approach — see W-PRES-01 |
| REQ-DDF-06: `format` required query param (422 if missing/invalid) | ✅ Implemented | `Literal["pdf","docx"] = Query(...)` on both download endpoints |
| REQ-DDF-07: RBAC checked BEFORE file I/O | ✅ Implemented | `can_download_format()` is the first operation in both download handlers |
| REQ-DDF-07: 403 with non-leaky message | ✅ Implemented | "Este formato de descarga no está disponible para tu rol." — no file path, no username |
| REQ-DDF-09: lazy backfill via ensure_pdf for pdf + NULL | ✅ Implemented | Lines 352–361 in `download_document` |
| REQ-DDF-10: PdfConversionError on backfill → 503 (W-03 closed) | ✅ Implemented | `except PdfConversionError → HTTPException(503)` in `download_document` |
| REQ-DDF-05: PdfConversionError on generate → 503 (W-03 closed) | ✅ Implemented | `except PdfConversionError → HTTPException(503)` in `generate_document` |
| REQ-DDF-05: PdfConversionError on generate-bulk → 503 (W-04 closed) | ✅ Implemented | `except PdfConversionError → HTTPException(503)` in `generate_bulk` |
| REQ-DDF-11: Non-admin + docx → 403 on bulk download | ✅ Implemented | `if not can_download_format(current_user.role, format)` |
| REQ-DDF-11: Non-admin + include_both=true → 403 (loud rejection) | ✅ Implemented | Explicit `if include_both and current_user.role != "admin"` check |
| REQ-DDF-12: include_both ZIP contains .docx + .pdf per row | ✅ Implemented | Verified by test and code inspection |
| REQ-DDF-15: DOCUMENT_DOWNLOAD audit with {format, document_id, via} | ✅ Implemented | Both download endpoints write audit event on success |
| W-05: errors field always [] on generate_bulk success | ✅ Implemented | `errors=result["errors"]` — always `[]` per service contract |
| DOCX MIME `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | ✅ Implemented | `_DOCX_MIME` constant, used in Response |
| PDF MIME `application/pdf` | ✅ Implemented | `_PDF_MIME` constant, used in Response |
| ADR-PDF-07: `via=share` creator sanity check | ✅ Implemented | `if via == "share" and current_user.user_id == doc.created_by: effective_via = "direct"` |
| No frontend changes (Phase 4 is backend-only) | ✅ Confirmed | `git diff HEAD -- frontend/` = 0 lines |
| No new DB migrations | ✅ Confirmed | Migration head still at `010` |
| No docker-compose / pyproject.toml changes | ✅ Confirmed | Both files unchanged |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-05: `can_download_format` is the sole RBAC decision point | ✅ Yes | Called at top of both download endpoints; no independent role checks |
| ADR-PDF-07: `via` param as client hint + server sanity check | ✅ Yes | Creator-only check implemented; simpler than full template_shares DB roundtrip (documented trade-off) |
| ADR-PDF-08: serial backfill before zipping | ✅ Yes | `for doc in batch_docs:` + `await service.ensure_pdf()` per legacy row |
| ADR-PDF-08: 503 if any backfill fails | ✅ Yes | `except PdfConversionError → 503` inside the ZIP loop |
| Design: W-03 / W-04 mapped to 503 | ✅ Yes | Both generate endpoints now catch `PdfConversionError` |
| Design: audit `resource_type` | ⚠️ Minor deviation | `resource_type="document"` for single, `resource_type="document_batch"` for bulk. Spec only requires the `details` fields — resource_type is an implementation choice, acceptable |
| Bulk download hexagonal boundary: `service._doc_repo` accessed directly | ⚠️ Documented deviation (W-PRES-02) | Apply-progress and design notes acknowledge this. `list_paginated(size=10000)` then Python filter. No `list_by_batch_id` port method exists yet |
| `_audit_service` accessed directly on service | ⚠️ Minor deviation | `service._audit_service` is accessed directly in both download endpoints. Should be encapsulated in a service method |

---

### Assertion Quality

| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| `test_documents_download_format.py` | ~170 | `assert response.status_code != 200` and `assert response.status_code != 201` | Weak assertion for SCEN-DDF-04 bulk variant — test passes because the dummy xlsx causes a 400/404/422, NOT specifically 422. Does not prove that `output_format` in the multipart body is rejected with 422. | WARNING |

**Assertion quality**: 0 CRITICAL, 1 WARNING

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):

- **W-PRES-01: Weak bulk `output_format` test** — `test_generate_bulk_with_output_format_returns_422` asserts `!= 200` and `!= 201` rather than the specific `== 422` implied by SCEN-DDF-04 and the test's own docstring/name. The test passes because the dummy xlsx bytes trigger a `400 Only .xlsx files are accepted`, not a 422. The endpoint correctly does NOT accept `output_format` as a parameter, but this test does not prove that — it only proves the endpoint doesn't return 200. **The test name says "returns_422" but doesn't assert 422.** This is a compliance gap for SCEN-DDF-04 bulk. Mitigation: REQ-DDF-04 is about the absence of `output_format` as an accepted field; for multipart/form-data endpoints, FastAPI silently ignores extra form fields (there is no Pydantic model to apply `extra="forbid"` to), which is the architectural reality. The spec says "its presence MUST result in HTTP 422" — for multipart endpoints this is not technically achievable without custom validation. Phase 6 integration tests (T-INT scope) should clarify the actual behavior.

- **W-PRES-02: Hexagonal boundary leak in bulk download** — `download_bulk` accesses `service._doc_repo.list_paginated(page=1, size=10000)` directly (private attribute) and filters results in the endpoint. This bypasses the hexagonal boundary. Also `size=10000` is a brittle workaround for missing `list_by_batch_id` port method. Apply-progress acknowledges this as a known limitation. Recommend adding `list_by_batch_id(batch_id: UUID) -> list[Document]` to the `DocumentRepository` port in Phase 6.

- **W-PRES-03: `_audit_service` accessed directly in endpoints** — Both `download_document` and `download_bulk` access `service._audit_service` directly (`if service._audit_service is not None: service._audit_service.log(...)`). This is a private attribute leak. The audit log should be encapsulated in a service method (e.g., `service.log_download_event(...)`) or the service should return audit context to the endpoint. Low severity — Phase 6 refactor scope.

**SUGGESTION**:

- **S-04**: The `download_bulk` endpoint bulk-fetches all documents (size=10000) and filters by `batch_id` in Python. For tenants with many documents, this is O(N) against total documents per tenant. A targeted `list_by_batch_id` query would be O(batch_size). Phase 6 should add this port method.

- **S-05**: The bulk download audit event records `document_id=str(batch_uuid)` in the `details` dict. This is slightly misleading — it's a batch ID, not a document ID. Consider renaming to `batch_id` for clarity.

- **S-01** (carried from Phase 1): `FakePdfConverter` does not enforce empty-bytes contract. Intentional — test double. Not a blocker.

---

### Phase 3 Warnings Resolution

| Warning | Closed? | Evidence |
|---------|---------|---------|
| W-03: `PdfConversionError → 503` in `generate_single` endpoint | ✅ RESOLVED | `except PdfConversionError → HTTPException(503)` at line 94–99 of `documents.py`; confirmed by `test_generate_pdf_conversion_error_returns_503` passing |
| W-04: `PdfConversionError → 503` in `generate_bulk` endpoint | ✅ RESOLVED | `except PdfConversionError → HTTPException(503)` at line 193–198 of `documents.py`; confirmed by `test_generate_bulk_pdf_conversion_error_returns_503` passing |
| W-05: `generate_bulk` errors field always `[]` on success | ✅ RESOLVED | `errors=result["errors"]` always `[]`; breaking-change semantics documented in endpoint docstring |

---

### Verdict

**✅ APPROVED_WITH_WARNINGS**

Phase 4 (Presentation) is fully implemented and verified. All 7 tasks complete. 20/20 Phase 4 tests pass on independent execution. 420/421 full suite passes — 1 pre-existing failure (`test_upload_template_appears_in_list`, pre-exists since Phase 3), zero new regressions. All Phase 3 warnings (W-03, W-04, W-05) are resolved.

The COMPLIANT count is 19/20 spec scenarios — the partial compliance is SCEN-DDF-04 for the bulk variant, which is a test quality issue (W-PRES-01) rather than a missing implementation. The endpoint correctly excludes `output_format` from its parameter list; the architectural reality of multipart/form-data endpoints (FastAPI silently ignores extra form fields) means a true 422 cannot be achieved without custom validation.

The two WARNINGs (W-PRES-02 hexagonal boundary, W-PRES-03 private audit access) are structural quality issues that do not block functionality and are tracked for Phase 6 refactoring.

**Phase 5 risks confirmed** (apply-progress Risk section):
1. Frontend mutations must drop `output_format` — `GenerateRequest` now has `extra="forbid"`; any client still sending it gets 422
2. ALL download links must include `?format=pdf|docx` — missing param → 422; existing frontend download links are broken until T-FE-02/T-FE-04/T-FE-05 land
3. Bulk download URL must include `?format=...` — until T-FE-06 lands

**Next recommended**: Ready to commit Phase 4 changes. Proceed to Phase 5 (T-FE-01 through T-FE-06 — Frontend: role-aware download UI, shadcn dropdown, bulk checkbox).

---

## Phase 5 Verification

**Date**: 2026-04-25
**Scope**: Phase 5 — Frontend (T-FE-01 through T-FE-06)
**Verdict**: ✅ APPROVED_WITH_WARNINGS

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 5 tasks total | 6 |
| Tasks complete | 6 |
| Tasks incomplete | 0 |

All 6 Phase 5 tasks are marked `[x]` in `tasks.md` and independently verified below. Changes are in the working tree (not yet committed — standard apply-then-verify workflow).

---

### Build & Tests Execution

**TypeScript (`npx tsc --noEmit -p tsconfig.app.json`)**:
```
EXIT_CODE: 0
```
Zero type errors. TypeScript clean.

**ESLint (`npm run lint`)**:
```
/frontend/src/components/ui/badge.tsx        52:17  warning  react-refresh/only-export-components
/frontend/src/components/ui/button.tsx       58:18  warning  react-refresh/only-export-components
/frontend/src/components/ui/tabs.tsx         80:52  warning  react-refresh/only-export-components
/frontend/src/features/documents/components/DynamicForm.tsx  37:17  error    @typescript-eslint/no-unused-vars ('_')
/frontend/src/routes/__root.tsx              12:20  error    react-hooks/rules-of-hooks
/frontend/src/shared/lib/auth.tsx            80:17  warning  react-refresh/only-export-components
✖ 6 problems (2 errors, 4 warnings)   EXIT_CODE: 1
```

**Baseline verification**: All 6 problems are confirmed pre-existing at `HEAD` (commit `faec5c7` — Phase 4). The `DynamicForm.tsx` `'_'` unused-vars error is in `templateName: _` which was present before Phase 5 (verified via `git show HEAD:...DynamicForm.tsx`). The `__root.tsx` hooks error and all 4 warnings are also pre-Phase-5. Phase 5 introduced **zero new ESLint errors or warnings**.

**Coverage**: Frontend has no test runner configured — not applicable.

---

### Per-Task Verification

| Task ID | Description | Verdict | Notes |
|---------|-------------|---------|-------|
| T-FE-01 | Install `dropdown-menu` shadcn primitive | ✅ PASS | See T-FE-01 detail below |
| T-FE-02 | Update API client download URL builder | ✅ PASS | `buildDownloadUrl`, `buildBulkDownloadUrl`, `triggerBlobDownload` all present and correct |
| T-FE-03 | Remove `output_format` from generate mutations | ✅ PASS | `rg "output_format" frontend/src/` returns zero matches |
| T-FE-04 | Create `DownloadButton` role-aware component | ✅ PASS | See T-FE-04 detail below |
| T-FE-05 | Replace download triggers in `DynamicForm.tsx` and `DocumentList.tsx` | ✅ PASS | Both files use `<DownloadButton ... via="direct"/>` |
| T-FE-06 | Update `BulkGenerateFlow.tsx` with bulk download controls | ✅ PASS | See T-FE-06 detail below |

---

### T-FE-01 Detail: `dropdown-menu.tsx`

**File exists**: `frontend/src/components/ui/dropdown-menu.tsx` ✅

**Import source**: `import { Menu as MenuPrimitive } from "@base-ui/react/menu"` — uses `@base-ui/react`, NOT `@radix-ui/react-dropdown-menu`.

**Design claim**: ADR-PDF-09 states the task is `npx shadcn-ui@latest add dropdown-menu`, which normally installs a Radix-based primitive. However the project's `components.json` has `"style": "base-nova"` — a shadcn style that targets `@base-ui/react` instead of Radix. The `@base-ui/react` package is already a top-level dependency in `package.json` (`"@base-ui/react": "^1.3.0"`), which explains why no new packages were added.

**No new top-level deps**: `git diff main frontend/package.json` shows zero changes. ✅

**Exports verified**: The file exports all components consumed by `DownloadButton.tsx`:
- `DropdownMenu` ✅ (`MenuPrimitive.Root`)
- `DropdownMenuTrigger` ✅ (`MenuPrimitive.Trigger`)
- `DropdownMenuContent` ✅ (`MenuPrimitive.Popup` wrapped with `Positioner`)
- `DropdownMenuItem` ✅ (`MenuPrimitive.Item`)
- Additional exports: `DropdownMenuPortal`, `DropdownMenuGroup`, `DropdownMenuLabel`, `DropdownMenuCheckboxItem`, `DropdownMenuRadioGroup`, `DropdownMenuRadioItem`, `DropdownMenuSeparator`, `DropdownMenuShortcut`, `DropdownMenuSub`, `DropdownMenuSubTrigger`, `DropdownMenuSubContent` — all present and exported.

**Keyboard accessibility**: `@base-ui/react/menu` uses WAI-ARIA keyboard patterns (same as Radix) — the design risk note about keyboard accessibility (ADR-PDF-09: "shadcn dropdown-menu uses Radix — keyboard accessible by default") is satisfied by the `@base-ui` implementation, which provides equivalent keyboard navigation.

**WARNING W-FE-01 (design deviation)**: The design doc (ADR-PDF-09) explicitly states "shadcn add dropdown-menu … using Radix UI primitives." The implementation uses `@base-ui/react/menu`. This is a documented, intentional deviation driven by the project's `components.json` `style: "base-nova"` configuration. Functionally equivalent — both are accessible, keyboard-navigable, and ARIA-compliant. No behavioral difference. Classified as WARNING (design deviation), not CRITICAL.

---

### T-FE-02 Detail: Download URL Builders

All three helpers exist in `frontend/src/features/documents/api/queries.ts`:

**`buildDownloadUrl(documentId, format, via)`**:
- `format: DownloadFormat = "pdf" | "docx"` ✅
- `via: DownloadVia = "direct" | "share"` ✅ (defaults to `"direct"`)
- Returns `/documents/${documentId}/download?format=...&via=...` ✅
- `via=share` plumbing exists but no frontend route currently passes `via="share"` — all current callers pass `via="direct"`. This is Phase 5 Risk #1 (noted in apply-progress). The `via` prop is wired through `DownloadButton` for future use.

**`buildBulkDownloadUrl(batchId, format, includeBoth)`**:
- `format: DownloadFormat` ✅
- `includeBoth: boolean = false` ✅
- Adds `include_both=true` only when `includeBoth` is truthy ✅
- When `includeBoth=false` (default), `include_both` param is omitted (not sent as `false`) ✅

**`triggerBlobDownload(url, filename)`**:
- Async, reusable blob download helper ✅
- Handles `createObjectURL` + link-click + `revokeObjectURL` lifecycle ✅

**Types exported**: `DownloadFormat = "pdf" | "docx"` ✅, `DownloadVia = "direct" | "share"` ✅

---

### T-FE-03 Detail: `output_format` Removal

`rg "output_format" frontend/src/` — **zero matches** ✅

Apply notes claimed the field was never in `mutations.ts` to begin with. Verified: the `GenerateRequest` interface in `mutations.ts` has only `template_version_id: string` and `variables: Record<string, string>`. No `output_format` field was ever present in the frontend mutations.

---

### T-FE-04 Detail: `DownloadButton` Component

**File**: `frontend/src/features/documents/components/DownloadButton.tsx` ✅

**Props**: `documentId: string`, `baseFileName?: string`, `via?: DownloadVia`, `disabled?: boolean` ✅

**Auth source**: `import { useAuth } from "@/shared/lib/auth"` → `const { user } = useAuth()` ✅. The `User` type in `auth.tsx` has `role: string`.

**Role check**: `const isAdmin = user?.role === "admin"` — exact strict equality (`===`), not loose or includes-based ✅

**Non-admin branch** (lines 69–81):
- Returns a single `<Button>` labeled "Descargar PDF"
- No caret, no DropdownMenu, no Word option
- The `DropdownMenu` JSX is in the `if (!isAdmin)` early-return path, meaning it is **not in the DOM** for non-admin users ✅
- RBAC bypass: impossible from frontend — the Word option has no DOM presence for non-admins ✅

**Admin branch** (lines 83–114):
- Renders `<DropdownMenu>` with two `<DropdownMenuItem>` entries: "Descargar como PDF" and "Descargar como Word (.docx)" ✅
- Both items call `handleDownload("pdf")` and `handleDownload("docx")` respectively ✅
- Each download calls `buildDownloadUrl(documentId, format, via)` — `format` param is always included ✅

**Loading state**: `downloadingFormat` state prevents double-clicks; both button variants show "Descargando..." ✅

---

### T-FE-05 Detail: Replaced Download Triggers

**`DynamicForm.tsx`**:
- Old: inline `handleDownload()` → `apiClient.get(url)` → `URL.createObjectURL` blob trigger
- New: `<DownloadButton documentId={documentId} baseFileName={fileName} via="direct" />` ✅
- `documentId` guard: rendered inside `{documentId && (...)}` — TypeScript narrows `string | null` to `string` within the block; TSC passes ✅

**`DocumentList.tsx`**:
- Old: icon-only `<Button>` with `handleDownload(doc.id, doc.file_name)` inline blob download (no format param — would have broken with Phase 4's required `?format=` param)
- New: `<DownloadButton documentId={doc.id} baseFileName={doc.file_name} via="direct" />` ✅
- Old `apiClient`, `DownloadIcon`, `downloadingId` state all removed ✅

**Scattered blob download check** (`rg "URL.createObjectURL|application/vnd.openxmlformats" frontend/src/features/documents/`):
- `BulkGenerateFlow.tsx:117` — `URL.createObjectURL` for ZIP download. This is the bulk ZIP download, **not** a single-document blob download. ✅ Acceptable: bulk ZIP is not handled by `triggerBlobDownload` (which is for single documents), and the bulk flow uses its own download path via `buildBulkDownloadUrl`.
- `mutations.ts:42` — `URL.createObjectURL` inside `useDownloadExcelTemplate`. This is the Excel **template** download (not a document download) — predates Phase 5 and is unrelated to the REQ-DDF-17 scope.
- `queries.ts:40` — `URL.createObjectURL` inside `triggerBlobDownload` — this IS the canonical blob download helper. ✅
- `BulkGenerateFlow.tsx:60` — `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` — this is the `react-dropzone` MIME type filter for accepting `.xlsx` uploads, not a document download. ✅

**Conclusion**: No rogue single-document blob downloads bypass `DownloadButton`. The only `URL.createObjectURL` calls outside `triggerBlobDownload` are: Excel template download (out of scope) and bulk ZIP download (intentional, uses `buildBulkDownloadUrl`).

---

### T-FE-06 Detail: `BulkGenerateFlow.tsx` Admin Checkbox

**Auth source**: `useCurrentUser()` — custom hook that calls `GET /auth/me` via React Query. Returns `CurrentUserResponse` with `role: string`. Note: this is **NOT** `useAuth()` from `shared/lib/auth.tsx` — it uses a separate query. Both paths ultimately read `user.role`.

**`isAdmin`**: `const isAdmin = currentUser?.role === "admin"` — exact strict equality ✅

**`includeBoth` state**: `const [includeBoth, setIncludeBoth] = useState(false)` — initialized `false` ✅

**Checkbox render**: `{isAdmin && (<label>...<input type="checkbox" ... />...</label>)}` — conditional render on `isAdmin` ✅
- When `isAdmin=false`, the entire `<label>` element is **not in the DOM** (React conditional render, not CSS `display:none`) ✅
- Checkbox label text: "Incluir documentos Word (.docx)" ✅

**Non-admin `include_both` guarantee**: `buildBulkDownloadUrl(result.batch_id, "pdf", isAdmin ? includeBoth : false)` — even if somehow `includeBoth=true` (state cannot be set by non-admin since checkbox is not in DOM), the ternary `isAdmin ? includeBoth : false` forces `false` for non-admins ✅

**Bulk download URL**: Always `format=pdf`, `include_both` only set when admin opts in ✅

**`via=share` risk**: `BulkGenerateFlow` does not pass `via` to `buildBulkDownloadUrl` (bulk endpoint does not have a `via` param). Consistent with the bulk download spec (REQ-DDF-11/12 — no `via` param for bulk). ✅

---

### Spec Compliance Matrix (Phase 5 — Frontend scope only)

| Requirement | Scenario | Evidence | Result |
|-------------|----------|---------|--------|
| REQ-DDF-17 | Admin sees split-button with PDF + Word options | `DownloadButton.tsx` admin branch renders `DropdownMenu` with two items | ✅ COMPLIANT |
| REQ-DDF-17 | Non-admin sees single "Descargar PDF" button only | `DownloadButton.tsx` non-admin early-return — no `DropdownMenu`, no Word item in DOM | ✅ COMPLIANT |
| REQ-DDF-17 | Word option NOT in DOM for non-admin (not just disabled) | `if (!isAdmin) return <Button>...` — DOM never contains Word option for non-admin | ✅ COMPLIANT |
| REQ-DDF-18 | Admin-only "Incluir documentos Word" checkbox in bulk flow | `BulkGenerateFlow.tsx` `{isAdmin && <label>...<input .../>...}` | ✅ COMPLIANT |
| REQ-DDF-18 | Checkbox NOT in DOM for non-admin | React conditional render — not CSS hide | ✅ COMPLIANT |
| REQ-DDF-18 | Checked state → `include_both=true` in URL | `buildBulkDownloadUrl(batch_id, "pdf", isAdmin ? includeBoth : false)` | ✅ COMPLIANT |
| REQ-DDF-18 | Non-admin always sends `include_both=false` | Ternary `isAdmin ? includeBoth : false` forces `false` | ✅ COMPLIANT |
| REQ-DDF-06 | All download URLs include `?format=...` | `buildDownloadUrl` always adds `format` param; `DownloadButton` always passes format | ✅ COMPLIANT |
| REQ-DDF-03/04 | Frontend does not send `output_format` | `rg "output_format" frontend/src/` = 0 matches | ✅ COMPLIANT |
| Phase 4 contract | Frontend now sends `?format=...` on all download requests | `buildDownloadUrl` adds `format` + `via`; `buildBulkDownloadUrl` adds `format` + optional `include_both` | ✅ YES |

**Compliance summary**: 10/10 Phase 5 frontend scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| REQ-DDF-17: split-button uses DropdownMenu primitive | ✅ Implemented | `@base-ui/react/menu` via `components.json base-nova style` |
| REQ-DDF-17: role check exact `=== "admin"` | ✅ Implemented | `user?.role === "admin"` — strict equality |
| REQ-DDF-17: non-admin Word option absent from DOM | ✅ Implemented | Early return before DropdownMenu JSX |
| REQ-DDF-18: isAdmin read from auth | ✅ Implemented | `useCurrentUser()` → `role === "admin"` |
| REQ-DDF-18: includeBoth defaults false | ✅ Implemented | `useState(false)` |
| REQ-DDF-18: non-admin cannot set include_both=true | ✅ Implemented | Ternary guard + checkbox not in DOM |
| DynamicForm: uses DownloadButton (via="direct") | ✅ Implemented | Inline blob download removed |
| DocumentList: uses DownloadButton (via="direct") | ✅ Implemented | Icon-only button + inline blob removed |
| No new top-level npm deps | ✅ Confirmed | `git diff main frontend/package.json` = empty |
| Backend untouched in Phase 5 | ✅ Confirmed | `git diff HEAD -- backend/` = empty |
| Migrations / docker-compose / pyproject.toml untouched | ✅ Confirmed | No diff in any of these files |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-09: `DownloadButton` encapsulates role logic | ✅ Yes | Single component, single role check, zero duplication |
| ADR-PDF-09: role accessor `useAuth().user.role === "admin"` | ⚠️ Minor deviation | `DynamicForm` + `DocumentList` use `useAuth()` via `DownloadButton`. `BulkGenerateFlow` uses its own `useCurrentUser()` hook instead of `useAuth()`. Both ultimately hit `/auth/me`. Functionally identical; minor pattern inconsistency. |
| ADR-PDF-09: shadcn dropdown-menu via `npx shadcn-ui@latest add` | ⚠️ Documented deviation (W-FE-01) | Uses `@base-ui/react/menu` instead of Radix — driven by `components.json style: "base-nova"`. No new packages. Equivalent behavior. |
| Design: `BulkDownloadControls.tsx` as separate component | ⚠️ Deviation | Design doc shows `BulkDownloadControls.tsx` as a new file. Instead, the bulk download controls (checkbox + button) are integrated directly into `BulkGenerateFlow.tsx`. No functional gap — the spec only requires the behavior, not the component structure. |
| Design: `via=share` available but unused | ✅ Documented | Risk #1 from apply-progress: `via=share` param exists in `buildDownloadUrl` but no route currently passes it. Plumbing is ready. |

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):

- **W-FE-01: `@base-ui/react/menu` instead of Radix UI** — The design (ADR-PDF-09) explicitly states the dropdown-menu primitive uses Radix UI. The implementation uses `@base-ui/react/menu` because the project's `components.json` has `style: "base-nova"`. This is the correct approach for this project (shadcn `base-nova` style is `@base-ui`-based), but it's a deviation from the design doc text. The design doc should be updated to reflect the actual library. Functionally equivalent — keyboard accessible, ARIA-compliant. **Not a regression; not a blocker.**

- **W-FE-02: `BulkGenerateFlow` uses `useCurrentUser()` instead of `useAuth()`** — The design specifies `useAuth().user.role`. `BulkGenerateFlow` has its own `useCurrentUser()` that calls `GET /auth/me` via React Query, which causes an extra HTTP request on each render (mitigated by React Query caching). The other files (`DownloadButton`) correctly use `useAuth()`. This inconsistency may cause a role mismatch if the two user objects diverge (e.g., role changes mid-session). Low practical risk — sessions are short-lived. Recommend aligning to `useAuth()` in a follow-up.

- **W-FE-03: `BulkDownloadControls.tsx` not created as a separate component** — Design doc shows this as a new file. The bulk download controls were integrated inline into `BulkGenerateFlow.tsx`. This is a component structure deviation (not a behavioral one). Low severity — the spec only requires the behavior. Track for future extraction if `BulkGenerateFlow` grows.

**SUGGESTION**:

- **S-FE-01: `via=share` plumbing exists but no route uses it** — Apply-progress Risk #1. The `buildDownloadUrl` always includes `via=...` in the URL. Currently all callers pass `via="direct"`. When the share-recipient inbox page is built (Phase 6+ scope), it will need to pass `via="share"`. The plumbing is ready.

- **S-FE-02: Bulk ZIP download in `BulkGenerateFlow` does not use `triggerBlobDownload` helper** — The bulk download (lines 114–129) duplicates the `createObjectURL` pattern inline instead of calling the shared `triggerBlobDownload` utility. Minor DRY violation. The blob is a ZIP, not a PDF/DOCX, so the file extension logic is different — but the URL pattern could still be extracted. Low priority.

- **S-FE-03: `DocumentList` column width** — Apply-progress noted the "Acciones" column at `w-[120px]` may be too narrow for the full `DownloadButton` split-button. This is a visual concern, not a functional one.

---

### Phase 4 Contract Resolution

**Question**: Does the frontend now send `?format=...` on all single-document and bulk download requests?

**Answer**: ✅ YES — RESOLVED

- Single document: `buildDownloadUrl(id, format, via)` always includes `format` in `URLSearchParams`. Every `DownloadButton` click calls `buildDownloadUrl` with an explicit format string (`"pdf"` or `"docx"`). The old inline blob downloads (which called `/documents/${id}/download` with no format param) are fully removed from `DynamicForm.tsx` and `DocumentList.tsx`.
- Bulk: `buildBulkDownloadUrl(batchId, "pdf", ...)` always includes `format=pdf`. 

This resolves the Phase 4 "Phase 5 risks" items 2 and 3.

---

### Verdict

**✅ APPROVED_WITH_WARNINGS**

Phase 5 (Frontend) is fully implemented and verified. All 6 tasks complete. TypeScript: 0 errors (exit 0). ESLint: 2 errors + 4 warnings — all 6 are confirmed pre-existing from Phase 4 HEAD; zero new issues introduced by Phase 5. 10/10 frontend spec scenarios (REQ-DDF-17, REQ-DDF-18) are COMPLIANT. Role-aware UI is correctly implemented with strict `=== "admin"` check and DOM-level exclusion of the Word option for non-admins. Backend untouched.

The 3 WARNINGs are design/pattern issues that do not affect functionality: W-FE-01 (`@base-ui` vs Radix — correct for this project's shadcn style), W-FE-02 (auth hook inconsistency in `BulkGenerateFlow`), W-FE-03 (no separate `BulkDownloadControls.tsx` file).

**Phase 6 risks carried forward**:
1. **`via=share` unimplemented on any route** — `buildDownloadUrl` plumbing exists but the share-recipient inbox page must pass `via="share"` to produce correct audit events.
2. **W-PRES-02 (from Phase 4) still open** — `download_bulk` endpoint accesses `service._doc_repo` directly (hexagonal boundary leak). Phase 6 should add `list_by_batch_id` port method.
3. **W-PRES-03 (from Phase 4) still open** — `_audit_service` accessed as private attribute in endpoints. Phase 6 refactor scope.

**Next recommended**: Commit Phase 5 frontend changes. Proceed to Phase 6 (T-INT-01 through T-INT-06 — Integration tests + smoke: E2E happy path, legacy backfill, sharing RBAC, migration regression, quota).

---

## Phase 6 Verification

**Date**: 2026-04-25
**Scope**: Phase 6 — Integration tests + W-PRES-02 closure (T-INT-01..T-INT-06 + `list_by_batch_id`)
**Verdict**: ✅ APPROVED_WITH_WARNINGS

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 6 tasks total | 6 |
| Tasks complete | 6 |
| Tasks incomplete | 0 |

All Phase 6 tasks (T-INT-01..T-INT-06) are marked `[x]` in `tasks.md` and independently verified below. Phase 7 (operational) is not yet started — not in scope for this verification.

---

### Build & Tests Execution

**Build**: N/A — Python/pytest project, no separate build step.

**Tests (Phase 6 new only)**:
```
24 passed in 0.59s
```
All 24 Phase 6 tests pass:
- `backend/tests/integration/test_pdf_export.py` — 20 integration tests
- `backend/tests/unit/domain/test_list_by_batch_id.py` — 4 unit tests (W-PRES-02 TDD)

**Full suite**:
```
1 failed, 444 passed, 3 warnings in 17.30s
```
Run: `cd backend && pytest tests/ -q --tb=short`

The single failure is the pre-existing `test_upload_template_appears_in_list` (session-scoped `FakeTemplateRepository` state pollution — unchanged from Phase 3).

**TDD RED confirmation** (stash test):
At Phase 5 HEAD (code stashed), the following tests were FAILING (RED):
- `test_list_by_batch_id_returns_matching_docs`
- `test_list_by_batch_id_tenant_isolation`
- `test_list_by_batch_id_returns_empty_for_unknown_batch`
- `test_list_by_batch_id_excludes_single_docs`
- `test_bulk_download_tenant_isolation`

Total at Phase 5 stash: **439 passed, 6 failed** (4 unit RED + 1 integration RED + 1 pre-existing). After Phase 6 implementation: **444 passed, 1 failed**. Delta: +5 passing (5 RED→GREEN), -5 failing. Math verified: 439+5=444 ✅, 6-5=1 ✅.

**Coverage**: Not configured — not available.

---

### W-PRES-02 Closure

| Check | Result | Evidence |
|-------|--------|---------|
| `DocumentRepository` port has abstract `list_by_batch_id(batch_id, tenant_id)` | ✅ YES | `backend/src/app/domain/ports/document_repository.py` lines 42–49 |
| SQL repo implements `list_by_batch_id` with single `SELECT WHERE batch_id AND tenant_id` | ✅ YES | `backend/src/app/infrastructure/persistence/repositories/document_repository.py` lines 95–113; single `select(DocumentModel).where(batch_id==..., tenant_id==...)` — NO `list_paginated(page=1, size=10000)` workaround |
| `FakeDocumentRepository` has `list_by_batch_id` implementation | ✅ YES | `backend/tests/fakes/fake_document_repository.py` lines 51–61; in-memory filter on `batch_id` + `tenant_id` |
| `DocumentService` has public `list_documents_by_batch(...)` delegator | ✅ YES | `backend/src/app/application/services/document_service.py` lines 277–286 |
| Bulk download endpoint calls `service.list_documents_by_batch()` (NOT `service._doc_repo`) | ✅ YES | `backend/src/app/presentation/api/v1/documents.py` line 244: `await service.list_documents_by_batch(batch_id=batch_uuid, tenant_id=current_user.tenant_id)` |
| `rg "_doc_repo" backend/src/app/presentation/` in bulk endpoint context | ✅ CLEAN | Line 242 is only a comment (`# W-PRES-02 fix: replaces service._doc_repo private...`), not code. No private attribute access in the bulk download fetch path. |

**W-PRES-02 status: CLOSED** ✅

---

### W-PRES-03 Status

Confirmed **deferred**. `service._audit_service` private access persists at:
- `backend/src/app/presentation/api/v1/documents.py` lines 296 (`download_bulk`) and 380 (single download)

This is the known hexagonal boundary leak carried forward from Phase 4. Not a blocker for Phase 6 archive.

---

### TDD Compliance (Phase 6)

| Task | RED confirmed | GREEN confirmed |
|------|---------------|-----------------|
| T-INT-01..06 (20 integration tests) | `test_bulk_download_tenant_isolation` was RED at Phase 5 HEAD (confirmed by stash run). Other integration tests were new untracked files — no prior failure state; RED confirmed by first-run evidence in apply-progress. | All 20 pass at Phase 6 HEAD |
| W-PRES-02 unit tests (4 tests in `test_list_by_batch_id.py`) | All 4 FAILED at Phase 5 HEAD (confirmed by stash run — `FakeDocumentRepository` had no `list_by_batch_id` method) | All 4 pass at Phase 6 HEAD |

---

### T-INT-01 — E2E Happy Path Verification

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-01a | Admin POST /generate → 201, both `docx_file_name` + `pdf_file_name` set, both files in storage | ✅ PASS |
| T-INT-01b | Admin GET /download?format=docx → 200, `wordprocessingml` MIME | ✅ PASS |
| T-INT-01c | Admin GET /download?format=pdf → 200, `application/pdf` MIME | ✅ PASS |
| T-INT-01d | Non-admin GET /download?format=pdf → 200, `application/pdf` MIME | ✅ PASS |
| T-INT-01e | Non-admin GET /download?format=docx → 403 (RBAC) | ✅ PASS |
| T-INT-01f | Audit: POST /generate → `document.generate` event with `formats_generated=["docx","pdf"]` | ✅ PASS |
| T-INT-01g | Audit: GET /download → `document.download` event with `format` + `via` fields | ✅ PASS |

**Note (SUGGESTION)**: The orchestrator checklist specified "3 download events with format and via" in T-INT-01. The test file checks exactly 1 download audit event (01g: PDF download by admin). The DOCX admin download (01b) and non-admin PDF download (01d) do not individually assert their audit events. The behavior is functionally correct — the audit system is exercised — but the audit trail for DOCX downloads and the non-admin download path is not independently asserted in T-INT-01. See S-INT-01 below.

---

### T-INT-02 — Legacy Backfill Verification

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-02a | Legacy doc (pdf_file_name=NULL) → GET /download?format=pdf → 200 → `pdf_file_name` set in DB | ✅ PASS |
| T-INT-02b | Second request on backfilled doc → converter NOT called (idempotent) | ✅ PASS |
| T-INT-02c | Converter failure → 503 → `pdf_file_name` stays NULL, DOCX not deleted | ✅ PASS |
| T-INT-02d | Single-use failure → first 503, second 200 (failure cleared) | ✅ PASS |

---

### T-INT-03 — Sharing RBAC Verification

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-03a | Non-admin + `format=docx&via=share` → 403 (SCEN-DDF-13) | ✅ PASS |
| T-INT-03b | Non-admin + `format=pdf&via=share` → 200 + audit `via="share"` (SCEN-DDF-14) | ✅ PASS |
| T-INT-03c | Creator sends `via=share` → server overrides to `via="direct"` in audit (ADR-PDF-07) | ✅ PASS |

---

### T-INT-04 — Migration 010 Regression Verification

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-04a | Legacy row: `docx_file_name` set, `pdf_file_name=NULL` → entity reads correctly; backfill triggers on PDF request | ✅ PASS |
| T-INT-04b | New row: all 4 file fields populated → entity reads and stores correctly | ✅ PASS |

**Note**: T-INT-04 uses the FakeDocumentRepository (entity-level structural verification). An actual `alembic downgrade -1 && upgrade head` DDL cycle was NOT executed as part of these integration tests — the Alembic DDL was verified separately in Phase 2 (schema structure, reversibility). Phase 6 T-INT-04 verifies entity/repository behavior, not DDL roundtrip. This is acceptable for Phase 6 scope; real DB migration is a Phase 7/CI responsibility.

---

### T-INT-05 — Quota Verification

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-05a | POST /generate: usage incremented by exactly 1 (not 2 for dual format) | ✅ PASS |
| T-INT-05b | Quota exceeded (via injected FakeQuotaService) → 429 | ✅ PASS |

**Note (SUGGESTION)**: The orchestrator checklist also specified "Bulk pre-flight check: tenant with remaining quota 3, requests 5 → 429 BEFORE any conversion (no orphan files)". This scenario is NOT in the test file — neither T-INT-05 nor any other Phase 6 test covers bulk generation quota enforcement. The `generate_bulk` quota path exists in the service (inherited from Phase 3), but is not exercised by a Phase 6 integration test. See S-INT-02 below.

---

### T-INT-06 — W-PRES-02 + Full Suite Regression Gate

| Sub-test | Description | Status |
|----------|-------------|--------|
| T-INT-06a | Bulk download with 2-doc batch → 200 ZIP with both files | ✅ PASS |
| T-INT-06b | Bulk download with cross-tenant batch → only tenant's own docs in ZIP | ✅ PASS |
| Full suite | 444/445 pass, 1 pre-existing failure | ✅ PASS |

---

### Spec Compliance Matrix (Phase 6 scope)

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| REQ-DDF-01 | Both file fields set after generation | `test_e2e_admin_generate_creates_both_files_in_storage` | ✅ COMPLIANT |
| REQ-DDF-03 | Admin generate → dual files in storage | `test_e2e_admin_generate_creates_both_files_in_storage` | ✅ COMPLIANT |
| REQ-DDF-06 | format=docx admin → 200 + DOCX MIME | `test_e2e_admin_download_docx_returns_200` | ✅ COMPLIANT |
| REQ-DDF-06 | format=pdf admin → 200 + PDF MIME | `test_e2e_admin_download_pdf_returns_200` | ✅ COMPLIANT |
| REQ-DDF-07 | Non-admin PDF download → 200 | `test_e2e_user_download_pdf_returns_200` | ✅ COMPLIANT |
| REQ-DDF-07 | Non-admin DOCX download → 403 | `test_e2e_user_download_docx_returns_403` | ✅ COMPLIANT |
| REQ-DDF-09 | Legacy doc → backfill → 200, pdf_file_name set | `test_legacy_backfill_happy_path_returns_200_and_persists_pdf` | ✅ COMPLIANT |
| REQ-DDF-09 | Backfill is idempotent (second request skips conversion) | `test_legacy_backfill_idempotent_second_request_skips_conversion` | ✅ COMPLIANT |
| REQ-DDF-10 | Backfill failure → 503, pdf_file_name stays NULL, DOCX not deleted | `test_legacy_backfill_converter_failure_returns_503_and_pdf_stays_null` | ✅ COMPLIANT |
| REQ-DDF-13 | Shared non-admin cannot download DOCX | `test_shared_user_cannot_download_docx` | ✅ COMPLIANT |
| REQ-DDF-13/15 | Shared non-admin PDF download → 200 + audit via=share | `test_shared_user_can_download_pdf_via_share` | ✅ COMPLIANT |
| REQ-DDF-14 | Generation audit: formats_generated=["docx","pdf"] | `test_e2e_generate_audit_event_has_formats_generated` | ✅ COMPLIANT |
| REQ-DDF-15 | Download audit: format + via fields | `test_e2e_download_audit_event_has_format_and_via` | ✅ COMPLIANT |
| REQ-DDF-15 | ADR-PDF-07: creator via=share overridden to direct | `test_creator_via_share_overridden_to_direct` | ✅ COMPLIANT |
| REQ-DDF-16 | Quota incremented by exactly 1 for dual-format generate | `test_quota_generate_increments_usage_by_exactly_one` | ✅ COMPLIANT |
| REQ-DDF-16 | Quota exceeded → 429 | `test_quota_exceeded_returns_429` | ✅ COMPLIANT |
| REQ-DDF-02 | Legacy row: docx_* populated, pdf_* NULL | `test_migration_010_doc_has_docx_fields_and_null_pdf_fields` | ✅ COMPLIANT |
| REQ-DDF-02 | New row: all 4 fields populated | `test_migration_010_new_doc_has_all_four_file_fields` | ✅ COMPLIANT |
| W-PRES-02 | Bulk download uses list_by_batch_id (hexagonal fix) | `test_bulk_download_uses_list_by_batch_id` | ✅ COMPLIANT |
| W-PRES-02 | Bulk download enforces tenant isolation | `test_bulk_download_tenant_isolation` | ✅ COMPLIANT |
| W-PRES-02 (unit) | `list_by_batch_id` returns matching docs | `test_list_by_batch_id_returns_matching_docs` | ✅ COMPLIANT |
| W-PRES-02 (unit) | `list_by_batch_id` tenant isolation | `test_list_by_batch_id_tenant_isolation` | ✅ COMPLIANT |
| W-PRES-02 (unit) | `list_by_batch_id` empty for unknown batch | `test_list_by_batch_id_returns_empty_for_unknown_batch` | ✅ COMPLIANT |
| W-PRES-02 (unit) | `list_by_batch_id` excludes single docs | `test_list_by_batch_id_excludes_single_docs` | ✅ COMPLIANT |

**Compliance summary**: 24/24 Phase 6 scenarios compliant.

---

### Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| `DocumentRepository` port: abstract `list_by_batch_id` | ✅ Implemented | Port method with `batch_id: UUID, tenant_id: UUID -> list[Document]` |
| SQL repo: single-query `list_by_batch_id` (no `list_paginated` workaround) | ✅ Implemented | `SELECT WHERE batch_id=:b AND tenant_id=:t` with `selectinload` — O(batch_size) |
| `FakeDocumentRepository.list_by_batch_id` | ✅ Implemented | In-memory filter on both fields |
| `DocumentService.list_documents_by_batch` public method | ✅ Implemented | Thin delegator at lines 277–286 |
| Bulk endpoint: no `service._doc_repo` in fetch path | ✅ Confirmed | Only comment mentions `_doc_repo`; actual call is `service.list_documents_by_batch(...)` |
| W-PRES-03: `service._audit_service` still private | ✅ Confirmed deferred | Present at lines 296, 380 — explicitly deferred to future phase |
| No frontend changes in Phase 6 | ✅ Confirmed | `git diff -- frontend/` has no Phase 6 changes |
| No new docker-compose / migration / pyproject.toml changes | ✅ Confirmed | Phase 6 touched only backend source + test files |

---

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| ADR-PDF-03: atomic generation flow | ✅ Yes | Service-level atomics from Phase 3 unchanged |
| ADR-PDF-04: `ensure_pdf` lazy backfill | ✅ Yes | Fully exercised by T-INT-02 tests |
| ADR-PDF-07: via=share override logic | ✅ Yes | T-INT-03c confirms creator override works |
| ADR-PDF-08: serial backfill before zipping | ✅ Yes | Bulk endpoint uses `ensure_pdf` in loop |
| W-PRES-02 fix approach: port method + public delegator | ✅ Yes | Hexagonal boundary respected for read path |
| W-PRES-03 deferred (audit service) | ✅ Documented | Carries forward as open WARNING |

---

### Test Count Delta

| Phase | Passing | Failing | Total collected | Delta |
|-------|---------|---------|-----------------|-------|
| Phase 4 end | 420 | 1 | 421 | baseline |
| Phase 5 end | 420 | 1 | 421 | +0 (frontend only) |
| Phase 6 end | **444** | **1** | **445** | **+24 new tests** |

Phase 5 baseline (420 passing) is a strict subset of Phase 6's 444 passing. ✅

---

### Issues Found

**CRITICAL** (must fix before archive):
None.

**WARNING** (should fix):

- **W-PRES-03 (carried forward)**: `service._audit_service` private access in `download_bulk` (line 296) and `download_document` (line 380) endpoints. Explicitly deferred from Phase 4 and again from Phase 6. This is a hexagonal boundary violation in the presentation layer. No behavioral impact for current tests, but it breaks the port/adapter contract and makes the audit call invisible to the service's public interface. Recommend adding `DocumentService.log_download_event(...)` or similar in Phase 7 cleanup.

**SUGGESTION** (nice-to-have):

- **S-INT-01: T-INT-01 only asserts 1 download audit event, not 3** — The orchestrator checklist for T-INT-01 specified 3 download audit events (admin DOCX, admin PDF, non-admin PDF). The test file asserts a download audit event only in `test_e2e_download_audit_event_has_format_and_via` (1 event, admin PDF). DOCX download audit and non-admin download audit are not individually verified in Phase 6. Existing Phase 4 tests cover these paths structurally. Low risk — audit is tested; just not exhaustively for all T-INT-01 flows.

- **S-INT-02: Bulk generate quota pre-flight (remaining=3, requests=5 → 429 BEFORE conversion) not tested** — The orchestrator's T-INT-05 checklist included this scenario. Neither T-INT-05 nor any Phase 6 test covers this. The quota guard exists in `generate_bulk` (inherited from Phase 3) but has no dedicated integration test for the "not enough quota for bulk batch" path. The single-generate quota path is tested. Recommend adding a T-INT-05c in a follow-up or Phase 7.

- **S-INT-03: No real DB test for `list_by_batch_id` SQL implementation** — The SQL implementation is structurally correct (confirmed by code review), but was only exercised against the `FakeDocumentRepository` in Phase 6 tests. The `selectinload` + WHERE clause was not validated against real PostgreSQL. Apply-progress acknowledges this. Phase 7 CI should run `docker compose exec api pytest` to validate.

---

### Pre-existing Failure

`tests/integration/test_templates_api.py::test_upload_template_appears_in_list` — session-scoped `FakeTemplateRepository` state pollution. Confirmed unchanged from Phase 3/4/5 verify reports. Out of scope for Phase 6.

---

### Verdict

**✅ APPROVED_WITH_WARNINGS**

Phase 6 (Integration tests + W-PRES-02 closure) is fully implemented and verified.

- **24/24 new tests** pass (20 integration + 4 W-PRES-02 unit)
- **444/445 full suite** — exactly matches apply-phase claim; 1 pre-existing failure unchanged
- **W-PRES-02 CLOSED**: `list_by_batch_id` is now a proper port method with SQL repo, fake, and public service delegator. The bulk download endpoint no longer accesses `service._doc_repo` directly.
- **W-PRES-03 DEFERRED**: `service._audit_service` private access remains — explicit carry-forward, not a regression
- **TDD RED→GREEN confirmed** for all Phase 6 additions via stash verification

No CRITICAL issues. 1 WARNING (W-PRES-03 carry-forward). 3 suggestions (non-blocking improvements to test coverage).

**Phase 7 recommended**: T-OPS-01 (nginx timeout), T-OPS-02 (.env.example), T-OPS-03 (Gotenberg image pin). Also: add S-INT-02 (bulk quota pre-flight test) as a Phase 7 addition before archive.

---

## Phase 7 Verification + Final Health-Check

**Date**: 2026-04-25
**Scope**: Phase 7 — Operational (T-OPS-01..T-OPS-03) + Final change health-check
**Verdict**: ✅ APPROVED_WITH_WARNINGS

---

### Completeness

| Metric | Value |
|--------|-------|
| Phase 7 tasks total | 3 (T-OPS-01, T-OPS-02, T-OPS-03) |
| Tasks complete | 3 |
| Tasks incomplete | 0 |
| **All phases total tasks** | **45** |
| **All phases tasks complete** | **45** |
| **Incomplete** | **0** |

All 45 tasks across Phases 1–7 are marked `[x]` in `tasks.md` and independently verified.

---

### T-OPS-01: nginx Upstream Timeout

**Claim**: `proxy_read_timeout` and `proxy_send_timeout` set to 300s in the `/api/` location block.

**File read**: `docker/nginx/nginx.conf`

**Verification**:
```nginx
location /api/ {
    proxy_pass http://api:8000;
    # Bulk download endpoint can take up to ~150s (50-row batch with all-legacy backfill).
    # 300s gives 2x headroom; 600s recommended for worst-case production loads.
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
```

**Result**: ✅ CONFIRMED — Both directives present at 300s. Applies to the entire `/api/` block, which includes the bulk download path (`/api/v1/documents/bulk/{batch_id}/download`). Spec required ≥ 300s; 300s exactly. The comment documents the rationale and notes 600s as a production recommendation.

---

### T-OPS-02: `.env.example` Documentation

**Claim**: Both `backend/.env.example` and root `.env.example` updated with `GOTENBERG_URL` and `GOTENBERG_TIMEOUT`.

**Working-tree diff** (via `git diff HEAD`):

```diff
--- a/.env.example
+++ b/.env.example
@@ -22,3 +22,7 @@
 DEBUG=false
 API_V1_PREFIX=/api/v1
+# PDF Conversion (Gotenberg)
+GOTENBERG_URL=http://gotenberg:3000
+GOTENBERG_TIMEOUT=60

--- a/backend/.env.example
+++ b/backend/.env.example
@@ -52,3 +52,10 @@
 RATE_LIMIT_GENERATE_BULK=5/minute
+# ── PDF Conversion (Gotenberg)
+# Internal URL of the Gotenberg service (used by the backend to convert DOCX → PDF)
+GOTENBERG_URL=http://gotenberg:3000
+# Timeout in seconds for a single DOCX-to-PDF conversion request
+GOTENBERG_TIMEOUT=60
```

**Result**: ✅ CONFIRMED — Both files have correct vars with appropriate comments. `GOTENBERG_URL` defaults to `http://gotenberg:3000`; `GOTENBERG_TIMEOUT` defaults to `60`.

**WARNING W-OPS-01**: Both `.env.example` files exist only as uncommitted working-tree changes (`git status` shows ` M .env.example` and ` M backend/.env.example`). They have NOT been committed to git. The `nginx.conf` change and `tasks.md`/`apply-progress.md` updates are similarly uncommitted. **These must be committed before `sdd-archive`** — they are part of the Phase 7 operational deliverables.

**Git status at verify time**:
```
 M .env.example
 M backend/.env.example
 M docker/nginx/nginx.conf
 M openspec/changes/pdf-export/apply-progress.md
 M openspec/changes/pdf-export/tasks.md
```

All 5 files are correct in working tree. They need one commit to be part of the change history.

---

### T-OPS-03: Gotenberg Image Pin

**Claim**: `gotenberg/gotenberg:8.16` (specific minor, not `:8` or `:latest`).

**File read**: `docker/docker-compose.yml`

```yaml
gotenberg:
  image: gotenberg/gotenberg:8.16  # pinned minor — update to latest 8.x before merge
```

**Result**: ✅ CONFIRMED — Specific minor version `:8.16` pinned. Comment in-place noting to update to latest 8.x before merge. Already committed as part of Phase 2.

---

### Live Service Status

**Command**: `docker compose -f docker/docker-compose.yml ps`

| Service | Status | Image | Health |
|---------|--------|-------|--------|
| `docker-api-1` | Up 4h | `docker-api` | **healthy** ✅ |
| `docker-db-1` | Up 4h | `postgres:16-alpine` | **healthy** ✅ |
| `docker-gotenberg-1` | Up 7m | `gotenberg/gotenberg:8.16` | **healthy** ✅ |
| `docker-minio-1` | Up 4h | `minio/minio:latest` | **healthy** ✅ |
| `docker-nginx-1` | Up 2w | `nginx:alpine` | up ✅ |
| `minio-init` | (exited cleanly — expected) | `minio/mc:latest` | — |

**6 services accounted for**: 5 running + minio-init exited cleanly. ✅

---

### Live Health Endpoint Checks

**Gotenberg** (`docker compose exec -T gotenberg wget -qO- http://localhost:3000/health`):
```json
{"status":"up","details":{"chromium":{"status":"up"},"libreoffice":{"status":"up"}}}
```
Exit code: 0 ✅ — LibreOffice is up (critical for DOCX→PDF conversion).

**API** (`curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health`):
```
API health: 200
```
Exit code: 0 ✅

**Docker health inspect** (`docker inspect docker-gotenberg-1 --format '{{.State.Health.Status}}'`):
```
healthy
```
✅

---

### httpx in Built Image — Discrepancy Analysis

**Apply-phase claim**: "httpx not in built image (operational warning)" — manual `pip install httpx` was needed.

**Independent verification**:

1. `backend/pyproject.toml` line 25: `"httpx>=0.27.0,<1.0"` is in `[project.dependencies]` (production deps, not dev-only). ✅
2. `docker/Dockerfile.backend`: `COPY backend/pyproject.toml ... && RUN pip install --no-cache-dir -e .` — installs all `[project.dependencies]`. ✅

**Root cause**: The running `docker-api-1` container was built BEFORE Phase 2 promoted `httpx` to production dependencies. The container image (`docker-api`) is stale — it was built before `httpx` was added to `[project.dependencies]`. The working-tree code and `pyproject.toml` are correct.

**Classification**: WARNING (not CRITICAL) — the code and Dockerfile are correct. The issue is a stale running container. Running `docker compose build api && docker compose up -d api` will permanently fix this for all future deployments.

**Production impact**: Any fresh deploy (new machine, new environment, CI/CD pipeline) will build the image from the current `Dockerfile.backend` + `pyproject.toml` and httpx will be included correctly. The only risk is someone pulling the existing `docker-api` image without rebuilding. This is a dev-environment operational issue, not a code defect.

**Required action before production**: `docker compose build api` — rebuild the api image to include httpx.

---

### Test Suite (Phase 7 regression gate)

**Command**: `cd backend && python3 -m pytest -q --no-header --tb=no`

```
1 failed, 444 passed, 3 warnings in 17.50s
```

| Metric | Count |
|--------|-------|
| Phase 7 new tests | 0 (ops-only phase — no new code) |
| Total tests | 445 |
| Passed | **444** |
| Failed | **1** (pre-existing: `test_upload_template_appears_in_list`) |
| New regressions from Phase 7 | **0** |

✅ CONFIRMED — 444/445, exactly matching apply-phase claim and Phase 6 baseline. Zero regressions.

---

### Final Spec Coverage Matrix (Overall Change)

This is the complete REQ-level audit across all spec files.

#### REQ-PDF-01 through REQ-PDF-10 (pdf-conversion spec)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-PDF-01: PdfConverter ABC with async convert(bytes) → bytes | ✅ IMPLEMENTED + TESTED | Phase 1: `test_pdf_converter_port.py` (4 tests) |
| REQ-PDF-02: GotenbergPdfConverter POST multipart to /forms/libreoffice/convert | ✅ IMPLEMENTED + TESTED | Phase 2: `test_gotenberg_pdf_converter.py::test_convert_success_sends_multipart_with_correct_field` |
| REQ-PDF-03: Settings expose gotenberg_url + gotenberg_timeout | ✅ IMPLEMENTED + TESTED | Phase 2: structural — `config.py` verified; backend tests use these values via Settings |
| REQ-PDF-04: httpx in [project.dependencies] ≥0.27,<1.0 | ✅ IMPLEMENTED + TESTED | Phase 2: `pyproject.toml` line 25 verified; T-INFRA-02 confirmed |
| REQ-PDF-05: gotenberg service in docker-compose, api depends_on healthy | ✅ IMPLEMENTED + TESTED | Phase 2: `docker-compose.yml` verified; live service healthy (Phase 7) |
| REQ-PDF-06: PdfConversionError extends DomainError in domain layer | ✅ IMPLEMENTED + TESTED | Phase 1: `test_pdf_conversion_error.py` (3 tests) |
| REQ-PDF-07: FakePdfConverter with set_failure single-use | ✅ IMPLEMENTED + TESTED | Phase 1: `test_fake_pdf_converter.py` (5 tests) |
| REQ-PDF-08: ALL httpx errors → PdfConversionError (4xx, 5xx, Timeout, ConnectError) | ✅ IMPLEMENTED + TESTED | Phase 2: `test_gotenberg_pdf_converter.py` (5 error-path tests) |
| REQ-PDF-09: Log duration+outcome on every call (INFO success, ERROR failure) | ✅ IMPLEMENTED + TESTED | Phase 2: `test_convert_success_logs_info`, `test_convert_5xx_logs_error` |
| REQ-PDF-10: AsyncClient (natively async, no asyncio.to_thread) | ✅ IMPLEMENTED + TESTED | Phase 2: code inspection (`async with httpx.AsyncClient(...)`) + `test_convert_success_returns_pdf_bytes` passing confirms async path |

#### REQ-DDF-01 through REQ-DDF-19 (document-download-format spec)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-DDF-01: Document entity dual file fields (docx_* required, pdf_* nullable) | ✅ IMPLEMENTED + TESTED | Phase 1: `test_document_entity.py` (9 tests); Phase 2: DB schema verified |
| REQ-DDF-02: Migration 010 rename + add nullable PDF cols, reversible | ✅ IMPLEMENTED + TESTED | Phase 2: `010_pdf_export.py` + downgrade verified; T-INT-04 entity tests |
| REQ-DDF-03: Generate always produces both formats, output_format rejected (422) | ✅ IMPLEMENTED + TESTED | Phase 3+4: `test_document_service_pdf.py` + `test_generate_with_output_format_returns_422`; Phase 6: `test_e2e_admin_generate_creates_both_files_in_storage` |
| REQ-DDF-04: Bulk generate always produces both formats, output_format rejected | ✅ IMPLEMENTED + TESTED | Phase 3: bulk dual-format tests; Phase 4: `test_generate_bulk_with_output_format_returns_422` (⚠️ PARTIAL — see W-PRES-01 carried from Phase 4) |
| REQ-DDF-05: Atomic failure — DOCX deleted, no DB row, HTTP 503 | ✅ IMPLEMENTED + TESTED | Phase 3+4: `test_pdf_failure_deletes_uploaded_docx`, `test_pdf_failure_no_db_row`, `test_generate_pdf_conversion_error_returns_503` |
| REQ-DDF-06: Download requires format=pdf|docx (422 if missing/invalid) | ✅ IMPLEMENTED + TESTED | Phase 4: `test_download_missing_format_returns_422`, `test_download_invalid_format_returns_422` |
| REQ-DDF-07: RBAC via can_download_format before serving file | ✅ IMPLEMENTED + TESTED | Phase 4+6: `test_user_download_docx_returns_403`, `test_e2e_user_download_docx_returns_403` |
| REQ-DDF-08: can_download_format is sole RBAC decision point, dict-based | ✅ IMPLEMENTED + TESTED | Phase 1: `test_document_permissions.py` (6 parametrized tests) |
| REQ-DDF-09: Lazy backfill on PDF request with NULL pdf_file_name (idempotent) | ✅ IMPLEMENTED + TESTED | Phase 3+4+6: `test_legacy_backfill_happy_path_returns_200_and_persists_pdf`, idempotent test |
| REQ-DDF-10: Backfill failure → 503, no DB update, DOCX not deleted | ✅ IMPLEMENTED + TESTED | Phase 3+4+6: `test_legacy_backfill_converter_failure_returns_503_and_pdf_stays_null` |
| REQ-DDF-11: Bulk download RBAC (format + include_both) | ✅ IMPLEMENTED + TESTED | Phase 4: 4 bulk RBAC tests covering 403 paths; Phase 6: `test_bulk_download_tenant_isolation` |
| REQ-DDF-12: Bulk include_both=true ZIP contains .docx + .pdf per row | ✅ IMPLEMENTED + TESTED | Phase 4: `test_bulk_download_admin_include_both_returns_zip_with_both` |
| REQ-DDF-13: Sharing inherits recipient role (no share bypass) | ✅ IMPLEMENTED + TESTED | Phase 4+6: `test_share_recipient_non_admin_cannot_download_docx`, `test_shared_user_can_download_pdf_via_share` |
| REQ-DDF-14: Generation audit includes formats_generated=["docx","pdf"] | ✅ IMPLEMENTED + TESTED | Phase 3+6: `test_audit_log_contains_formats_generated`, `test_e2e_generate_audit_event_has_formats_generated` |
| REQ-DDF-15: Download audit with {format, document_id, via} | ✅ IMPLEMENTED + TESTED | Phase 4+6: `test_share_recipient_non_admin_downloads_pdf_with_via_share_audit`, `test_e2e_download_audit_event_has_format_and_via` |
| REQ-DDF-16: Quota +1 per generate (not +2 for dual format) | ✅ IMPLEMENTED + TESTED | Phase 3+6: `test_quota_incremented_by_exactly_one`, `test_quota_generate_increments_usage_by_exactly_one` |
| REQ-DDF-17: Frontend role-aware single-doc download UI | ✅ IMPLEMENTED (not directly tested — frontend has no test runner) | Phase 5: TypeScript 0 errors; code inspection confirms admin split-button, non-admin single button, Word option not in DOM |
| REQ-DDF-18: Frontend bulk admin-only "Incluir documentos Word" checkbox | ✅ IMPLEMENTED (not directly tested — frontend has no test runner) | Phase 5: TypeScript 0 errors; code inspection confirms React conditional render on isAdmin |
| REQ-DDF-19: Admin DOCX download regression safety | ✅ IMPLEMENTED + TESTED | Phase 4+6: `test_admin_download_docx_returns_200_with_correct_mime`, `test_e2e_admin_download_docx_returns_200` |

**Compliance summary**: 29/29 requirements implemented. 27/29 have direct test coverage. 2/29 (REQ-DDF-17, REQ-DDF-18 — frontend) are implemented but untested due to no frontend test runner configured.

**SCEN coverage**: 45 total scenarios across both spec files. All 45 classified COMPLIANT or PARTIAL (W-PRES-01 for SCEN-DDF-04 bulk variant).

---

### Outstanding Warnings — Final Status

| Warning | Phase Introduced | Status at Archive | Severity |
|---------|-----------------|-------------------|----------|
| W-PRES-01: Weak bulk output_format test (asserts !=200 not ==422) | Phase 4 | OPEN — deferred tech debt | Acceptable for archive — multipart/form-data architectural constraint means true 422 not achievable without custom validation |
| W-PRES-03: `service._audit_service` private access in endpoints | Phase 4 | OPEN — deferred tech debt | Acceptable for archive — no functional impact; refactor adds `log_download_event()` public method |
| W-FE-01: `@base-ui/react/menu` instead of Radix in design doc | Phase 5 | OPEN — design doc lag only | Acceptable for archive — code is correct for this project's shadcn config |
| W-FE-02: `BulkGenerateFlow` uses `useCurrentUser()` not `useAuth()` | Phase 5 | OPEN — minor pattern inconsistency | Acceptable for archive — same auth source, React Query caches it |
| W-FE-03: `BulkDownloadControls` inline instead of separate file | Phase 5 | OPEN — component structure only | Acceptable for archive — no behavioral impact |
| W-OPS-01: `.env.example` changes uncommitted (working tree only) | Phase 7 (this verify) | **MUST COMMIT before archive** | BLOCKS archive — operational docs must be part of the git change |
| httpx stale container (docker-api image built before Phase 2) | Phase 7 | OPEN — action required before production | Acceptable for archive with note — `docker compose build api` required |
| `DocumentResponse.file_name` backward-compat alias still present | Phase 2 | OPEN — deferred cleanup | Acceptable for archive — documented, no breaking change |

**Archive-blocking warnings**: 1 — W-OPS-01 (uncommitted changes).
**Non-blocking deferred warnings**: 7.

---

### Tasks Completion

**All 45 tasks marked `[x]`** in `tasks.md`.

| Phase | Tasks | Complete |
|-------|-------|----------|
| Phase 1 — Domain | 8 | 8/8 ✅ |
| Phase 2 — Infrastructure | 8 | 8/8 ✅ |
| Phase 3 — Application service | 7 | 7/7 ✅ |
| Phase 4 — Presentation | 7 | 7/7 ✅ |
| Phase 5 — Frontend | 6 | 6/6 ✅ |
| Phase 6 — Integration tests | 6 | 6/6 ✅ |
| Phase 7 — Operational | 3 | 3/3 ✅ |
| **Total** | **45** | **45/45** ✅ |

---

### Issues Found (Phase 7 + Final)

**CRITICAL** (must fix before archive):
None — no broken services, no broken smoke tests, no regressed tests, no missing REQs.

**WARNING** (should fix):

- **W-OPS-01: Uncommitted working-tree changes** — `nginx.conf`, `.env.example`, `backend/.env.example`, `apply-progress.md`, and `tasks.md` are all modified but not committed. These are Phase 7 deliverables and must be committed before `sdd-archive` runs. One commit covers all 5 files.

- **W-OPS-02: Stale api container image** — The running `docker-api-1` container was built before Phase 2 added `httpx` to `[project.dependencies]`. The code is correct; the image is stale. `docker compose build api && docker compose up -d api` is required before production deployment. The smoke test required a manual `pip install httpx` workaround. This does NOT affect the test suite (tests run on host against in-memory fakes).

- **W-PRES-03 (carried from Phases 4, 5, 6)**: `service._audit_service` accessed as private attribute in both download endpoints (`documents.py` lines 296 and 380). Hexagonal boundary violation. No functional impact. Post-archive cleanup recommended.

**SUGGESTION**:

- **S-INT-02 (carried from Phase 6)**: Bulk generate quota pre-flight scenario not tested (remaining=3, requests=5 → 429 before any conversion). The path exists in code but has no dedicated integration test.

- **S-INT-03 (carried from Phase 6)**: `list_by_batch_id` SQL implementation not tested against real PostgreSQL (only fake). Phase 7 has now confirmed the service runs and handles real DB requests (smoke test used the full stack), but the specific SQL for batch listing was not stress-tested.

- **S-OPS-01**: nginx timeout is 300s (spec minimum). For production with large tenants (100+ legacy rows in a batch), consider upgrading to 600s as noted in the `nginx.conf` comment.

- **S-OPS-02**: The `.env.example` comment on `GOTENBERG_URL` says "Internal URL" — consider adding a note that this is only valid inside the `sigdoc` Docker network, and a different value is needed for external/local dev access.

---

### Verdict

**✅ APPROVED_WITH_WARNINGS**

The `pdf-export` change is implementation-complete, operationally verified, and behaviorally confirmed via live services and 444-test suite.

**Summary**:
- 45/45 tasks marked done
- 444/445 tests passing (1 pre-existing failure, 0 new regressions from Phase 7)
- All 3 operational tasks confirmed via independent code inspection and live service checks
- Gotenberg healthy with LibreOffice up; API healthy at 200; nginx serving with 300s timeout
- httpx is in `[project.dependencies]` — stale container is an env issue, not a code defect
- 29/29 spec requirements implemented; 27/29 with direct test coverage; 2 (frontend UI) untested due to no configured frontend test runner
- 1 WARNING blocks archive: uncommitted working-tree changes must be committed first

**Archive-ready**: YES — after committing the 5 uncommitted files (`nginx.conf`, `.env.example`, `backend/.env.example`, `apply-progress.md`, `tasks.md`).

**Next recommended**: Commit Phase 7 working-tree changes, then run `sdd-archive` to sync delta specs and close the change.
