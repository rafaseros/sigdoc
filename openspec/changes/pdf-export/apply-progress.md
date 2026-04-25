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

- Phase 3 — Application service layer: T-APP-01..T-APP-07
- Phase 4 — Presentation (endpoints + RBAC + audit): T-PRES-01..T-PRES-07
- Phase 5 — Frontend: T-FE-01..T-FE-06
- Phase 6 — Integration tests + smoke: T-INT-01..T-INT-06
- Phase 7 — Operational: T-OPS-01..T-OPS-03

---

## Phase 2 — Infrastructure (COMPLETE)

**Batch**: 2 of N  
**Mode**: Strict TDD  
**Date**: 2026-04-25

---

## Tasks Status

| Task ID | Description | Status |
|---------|-------------|--------|
| T-INFRA-01 | Add Gotenberg config to `Settings` | ✅ DONE |
| T-INFRA-02 | Promote `httpx` and add `respx` dev dep | ✅ DONE |
| T-INFRA-03 | Update `DocumentModel` SQLAlchemy columns | ✅ DONE |
| T-INFRA-04 | Create Alembic migration `010_pdf_export.py` | ✅ DONE |
| T-INFRA-05 | Add `update_pdf_fields` to `DocumentRepository` | ✅ DONE |
| T-INFRA-06 | [TEST] Adapter unit tests for `GotenbergPdfConverter` | ✅ DONE |
| T-INFRA-07 | Implement `GotenbergPdfConverter` adapter + `__init__.py` factory | ✅ DONE |
| T-INFRA-08 | Add `gotenberg` service to `docker-compose.yml` | ✅ DONE |

---

## TDD Cycle Evidence (Phase 2)

| Task | RED | GREEN |
|------|-----|-------|
| T-INFRA-06/07 | 9 FAILED (ModuleNotFoundError) | 9 PASSED |

Groups A, B, D, E were configuration/structural changes — no RED/GREEN cycle required (no dedicated tests for config keys, migration DDL, or docker-compose).
T-INFRA-03/04: verified via `alembic upgrade head` + `psql \d documents` + `downgrade -1` + `upgrade head`.

---

## Files Created (Phase 2)

| File | Description |
|------|-------------|
| `backend/alembic/versions/010_pdf_export.py` | Migration: rename file_name→docx_file_name, minio_path→docx_minio_path; add pdf_file_name/pdf_minio_path nullable |
| `backend/src/app/infrastructure/pdf/__init__.py` | `@lru_cache get_pdf_converter()` factory mirroring get_storage_service() pattern |
| `backend/src/app/infrastructure/pdf/gotenberg_pdf_converter.py` | `GotenbergPdfConverter` using httpx.AsyncClient with configurable timeout |
| `backend/tests/unit/infrastructure/__init__.py` | New test package |
| `backend/tests/unit/infrastructure/test_gotenberg_pdf_converter.py` | 9 tests covering SCEN-PDF-01..05 + logging |

## Files Modified (Phase 2)

| File | Change |
|------|--------|
| `backend/src/app/config.py` | Added `gotenberg_url` (default `http://gotenberg:3000`) and `gotenberg_timeout` (default `60`) |
| `backend/pyproject.toml` | Promoted `httpx>=0.27.0,<1.0` to `[project.dependencies]`; added `respx>=0.20.0,<1.0` to dev deps; removed `httpx` from dev deps |
| `backend/src/app/infrastructure/persistence/models/document.py` | Renamed `file_name`→`docx_file_name`, `minio_path`→`docx_minio_path`; added `pdf_file_name` (nullable) and `pdf_minio_path` (nullable) |
| `backend/src/app/infrastructure/persistence/repositories/document_repository.py` | Removed TODO comment; updated `_to_orm()` to use canonical docx_* + pdf_* column names; added `update_pdf_fields()` method |
| `backend/src/app/application/services/document_service.py` | Updated `get_document` and `delete_document` to use `document.docx_minio_path` (ORM column now renamed) |
| `backend/src/app/presentation/api/v1/documents.py` | Updated all `doc.file_name` → `doc.docx_file_name`, `doc.minio_path` → `doc.docx_minio_path` across generate, list, get_document, download endpoints |
| `backend/src/app/presentation/schemas/document.py` | Added `docx_file_name`, `pdf_file_name` fields; kept `file_name` as computed alias (option a — backward compat); added `model_validator` |
| `backend/src/app/domain/entities/document.py` | **Removed** `file_name` and `minio_path` backward-compat property aliases (W-01 resolved) |
| `backend/tests/unit/domain/test_document_entity.py` | Updated alias tests to verify aliases are GONE (Phase 2 assertion) |
| `docker/docker-compose.yml` | Added `gotenberg` service with `gotenberg/gotenberg:8.16`, healthcheck, sigdoc network; added `gotenberg: condition: service_healthy` to `api.depends_on` |

---

## Migration Testing (Phase 2)

| Step | Result |
|------|--------|
| `alembic upgrade head` (009→010) | ✅ Success |
| `psql \d documents` — verify new columns | ✅ `docx_file_name`, `docx_minio_path`, `pdf_file_name`, `pdf_minio_path` all present |
| `alembic downgrade -1` (010→009) | ✅ Success — columns renamed back, PDF columns dropped |
| `alembic upgrade head` (009→010 again) | ✅ Success — DB left in correct final state |

---

## Test Results (Phase 2)

| Metric | Count |
|--------|-------|
| Phase 2 new tests | 9 |
| Phase 1 tests | 29 |
| Pre-Phase-1 baseline | 347 |
| Total after Phase 2 | 384 |
| Regressions | 0 |

---

## Key Decision: DocumentResponse.file_name (option a — backward compat)

### Decision
Chose **option (a)**: Keep `DocumentResponse.file_name` populated from `docx_file_name` via a `model_validator`. Added explicit `docx_file_name` and `pdf_file_name` fields.

### Rationale
- Option (b) (hard rename to `docx_file_name`) would break the frontend immediately — Phase 5 hasn't landed yet.
- Option (c) (re-introduce entity alias) was rejected — the entity alias was already removed (W-01 fix).
- Option (a) is additive: no frontend breakage, new fields available for Phase 5 migration, `file_name` removed after Phase 5 lands.

---

## W-01 Resolved

The `file_name` and `minio_path` property aliases on the `Document` entity have been removed. All consumers updated:
- `document_service.py`: uses `docx_minio_path` directly on ORM objects
- `documents.py` endpoint: uses `docx_file_name`/`docx_minio_path` on ORM objects
- `document_repository.py`: uses canonical column names
- `schemas/document.py`: `file_name` kept as computed value from `docx_file_name` (backward compat, see decision above)
- `test_document_entity.py`: alias tests updated to assert aliases are absent

---

## Risks / Blockers for Phase 3

1. **`DocumentService` needs `pdf_converter` parameter** (T-APP-02): `__init__` must be extended to accept `PdfConverter | None` (optional for backward compat during transition). The `get_pdf_converter()` factory is ready.
2. **`get_document_service` DI factory** (T-APP-07): must pass `get_pdf_converter()` as a new kwarg — trivial once T-APP-02 lands.
3. **`update_pdf_fields` in repository returns `DocumentModel`** — Phase 3's `ensure_pdf` must be aware it receives an ORM object, not a domain `Document` entity. Consider adding a proper `_to_entity()` method in Phase 3 for clean hexagonal boundary.
4. **Gotenberg not yet running** (by design — T-OPS scope): `api` service `depends_on: gotenberg: condition: service_healthy` in compose means `docker compose up api` will wait for Gotenberg healthcheck. This is intentional — Phase 7 brings it up operationally.
