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
