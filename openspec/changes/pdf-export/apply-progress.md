# Apply Progress — pdf-export

## Phase 1: Domain & permissions (COMPLETE)

**Batch**: 1 of N  
**Mode**: Strict TDD  
**Date**: 2026-04-25

---

## Tasks Status

| Task ID | Description | Status |
|---------|-------------|--------|
| T-DOMAIN-01 | [TEST] Unit tests for `can_download_format` truth table | ✅ DONE |
| T-DOMAIN-02 | Implement `can_download_format` permission helper | ✅ DONE |
| T-DOMAIN-03 | Add `PdfConversionError` to domain exceptions | ✅ DONE |
| T-DOMAIN-04 | Define `PdfConverter` port interface | ✅ DONE |
| T-DOMAIN-05 | [TEST] Contract tests for `FakePdfConverter` | ✅ DONE |
| T-DOMAIN-06 | Implement `FakePdfConverter` test double | ✅ DONE |
| T-DOMAIN-07 | Add `AuditAction.DOCUMENT_DOWNLOAD` to audit entity | ✅ DONE |
| T-DOMAIN-08 | Update `Document` entity with dual file fields | ✅ DONE |

---

## TDD Cycle Evidence

| Task | RED | GREEN |
|------|-----|-------|
| T-DOMAIN-01/02 | 6 FAILED (ModuleNotFoundError) | 6 PASSED |
| T-DOMAIN-03 | 3 FAILED (ImportError) | 3 PASSED |
| T-DOMAIN-04 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-05/06 | 5 FAILED (ModuleNotFoundError) | 5 PASSED |
| T-DOMAIN-07 | 1 FAILED (AssertionError) | 1 PASSED |
| T-DOMAIN-08 | 8 FAILED (TypeError/AssertionError) | 9 PASSED |

---

## Files Created

| File | Description |
|------|-------------|
| `backend/src/app/domain/services/__init__.py` | Empty package init |
| `backend/src/app/domain/services/document_permissions.py` | `DOWNLOAD_FORMAT_PERMISSIONS` dict + `can_download_format()` |
| `backend/src/app/domain/ports/pdf_converter.py` | `PdfConverter` ABC with async `convert(docx_bytes: bytes) -> bytes` |
| `backend/tests/fakes/fake_pdf_converter.py` | `FakePdfConverter` with `set_failure()` single-use API |
| `backend/tests/unit/domain/__init__.py` | New test package |
| `backend/tests/unit/domain/test_document_permissions.py` | 6 parametrized truth-table tests (SCEN-DDF-16) |
| `backend/tests/unit/domain/test_pdf_conversion_error.py` | 3 tests for `PdfConversionError` |
| `backend/tests/unit/domain/test_pdf_converter_port.py` | 5 tests for `PdfConverter` ABC contract |
| `backend/tests/unit/domain/test_fake_pdf_converter.py` | 5 contract tests for `FakePdfConverter` |
| `backend/tests/unit/domain/test_audit_action_download.py` | 1 test for `DOCUMENT_DOWNLOAD` constant |
| `backend/tests/unit/domain/test_document_entity.py` | 9 tests for renamed `Document` fields |

## Files Modified

| File | Change |
|------|--------|
| `backend/src/app/domain/exceptions.py` | Added `PdfConversionError(DomainError)` |
| `backend/src/app/domain/entities/audit_log.py` | Added `DOCUMENT_DOWNLOAD = "document.download"` |
| `backend/src/app/domain/entities/document.py` | Renamed `file_name`→`docx_file_name`, `minio_path`→`docx_minio_path`; added `pdf_file_name: str | None` and `pdf_minio_path: str | None`; added backward-compat read-only property aliases |
| `backend/src/app/application/services/document_service.py` | Updated `Document()` constructor calls to use `docx_file_name=` / `docx_minio_path=` |
| `backend/src/app/infrastructure/persistence/repositories/document_repository.py` | Updated `_to_orm()` to read `document.docx_file_name` / `document.docx_minio_path` |
| `backend/tests/fakes/__init__.py` | Added `FakePdfConverter` export |

---

## Test Results

| Metric | Count |
|--------|-------|
| Phase 1 new tests | 29 |
| Original suite (pre-Phase 1) | 347 |
| Total after Phase 1 | 375 |
| Regressions | 0 |

---

## Key Decision: Document Entity Alias Strategy

### Decision
Use backward-compat read-only property aliases `file_name` and `minio_path` on the `Document` dataclass during Phase 1. Aliases return `docx_file_name` and `docx_minio_path` respectively.

### Rationale
The rename blast radius spans multiple layers. The SQLAlchemy model (`DocumentModel`) still uses `file_name`/`minio_path` column names and cannot be renamed without an Alembic migration (Phase 2). Aliases prevent 19 test regressions while keeping the domain entity correct.

### Write call sites updated (Phase 1)
- `document_service.py`: `Document()` constructors now use `docx_file_name=` / `docx_minio_path=`
- `document_repository.py`: `_to_orm()` reads `document.docx_file_name` / `document.docx_minio_path`

### Read call sites deferred (resolved in Phase 2)
- `documents.py` endpoint: `doc.file_name`, `doc.minio_path` — work via property alias on domain entity; on `DocumentModel` (returned by SQLAlchemy), they go to the ORM column directly (still `file_name`/`minio_path` until migration)
- `schemas/document.py`: `DocumentResponse.file_name` field name unchanged (API backward compat)

---

## Phase 2 Required Actions (for next batch)

1. **SQLAlchemy model**: Rename `file_name` → `docx_file_name`, `minio_path` → `docx_minio_path` on `DocumentModel`
2. **Alembic migration** `010_pdf_export.py`: Rename DB columns + add `pdf_file_name`/`pdf_minio_path` nullable columns
3. **document_repository.py** `_to_orm()`: Remove TODO comment; field names will match after migration
4. **documents.py endpoint**: Update `doc.file_name` → `doc.docx_file_name`, `doc.minio_path` → `doc.docx_minio_path` after ORM rename
5. **schemas/document.py**: Consider renaming `DocumentResponse.file_name` to `docx_file_name` (breaking API change — evaluate carefully)
6. **Remove aliases**: Remove `file_name` and `minio_path` properties from `Document` entity once all consumers updated

---

## Phases Remaining

- Phase 2 — Infrastructure (DB, deps, docker, adapter): T-INFRA-01..T-INFRA-08
- Phase 3 — Application service layer: T-APP-01..T-APP-07
- Phase 4 — Presentation (endpoints + RBAC + audit): T-PRES-01..T-PRES-07
- Phase 5 — Frontend: T-FE-01..T-FE-06
- Phase 6 — Integration tests + smoke: T-INT-01..T-INT-06
- Phase 7 — Operational: T-OPS-01..T-OPS-03
