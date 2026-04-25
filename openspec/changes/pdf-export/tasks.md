# Tasks — pdf-export

## Conventions
- **Strict TDD**: every implementation task is preceded by a `[TEST]` task
- **Task IDs**: `T-<PHASE>-<NN>` (e.g., T-DOMAIN-01, T-INFRA-05)
- **Done when**: code committed, related tests pass, no regressions in existing suite
- **Depends on**: listed task IDs must be committed before starting this task

---

## Phase 1 — Domain & permissions (foundation, no infra deps)

### T-DOMAIN-01: [x] [TEST] Unit tests for `can_download_format` truth table
- **Files**: `backend/tests/unit/domain/test_document_permissions.py`
- **REQs**: REQ-DDF-08, SCEN-DDF-16
- **Depends on**: —
- **Description**: Write parametrized pytest covering all 6 cases: `(admin,docx)→T`, `(admin,pdf)→T`, `(user,docx)→F`, `(user,pdf)→T`, `(unknown,docx)→F`, `(unknown,pdf)→T`. Tests must FAIL (red) before T-DOMAIN-02 is written.

### T-DOMAIN-02: [x] Implement `can_download_format` permission helper
- **Files**: `backend/src/app/domain/services/__init__.py`, `backend/src/app/domain/services/document_permissions.py`
- **REQs**: REQ-DDF-08
- **Depends on**: T-DOMAIN-01
- **Description**: Create `domain/services/` directory (new — does not exist). Implement `DOWNLOAD_FORMAT_PERMISSIONS` dict and `can_download_format(role, format) -> bool`. Unknown role defaults to `frozenset({"pdf"})`. This is the ONLY RBAC decision point for format.

### T-DOMAIN-03: [x] Add `PdfConversionError` to domain exceptions
- **Files**: `backend/src/app/domain/exceptions.py`
- **REQs**: REQ-PDF-06
- **Depends on**: —
- **Description**: Add `class PdfConversionError(DomainError)` accepting `message: str`. Must be in the domain layer (not infrastructure). Existing `DomainError` base class is already present in this file.

### T-DOMAIN-04: [x] Define `PdfConverter` port interface
- **Files**: `backend/src/app/domain/ports/pdf_converter.py`
- **REQs**: REQ-PDF-01, REQ-PDF-10
- **Depends on**: T-DOMAIN-03
- **Description**: Create `class PdfConverter(ABC)` with `@abstractmethod async def convert(self, docx_bytes: bytes) -> bytes`. Must raise only `PdfConversionError`. The `ports/` directory already exists.

### T-DOMAIN-05: [x] [TEST] Contract tests for `FakePdfConverter`
- **Files**: `backend/tests/unit/domain/test_fake_pdf_converter.py`
- **REQs**: REQ-PDF-07, SCEN-PDF-06
- **Depends on**: T-DOMAIN-04
- **Description**: Write tests asserting: success mode returns `convert_result` bytes; `set_failure(exc)` causes next call to raise that exception; failure state clears after single use (subsequent call succeeds). Must FAIL (red) before T-DOMAIN-06.

### T-DOMAIN-06: [x] Implement `FakePdfConverter` test double
- **Files**: `backend/tests/fakes/fake_pdf_converter.py`
- **REQs**: REQ-PDF-07
- **Depends on**: T-DOMAIN-05
- **Description**: Implements `PdfConverter` with configurable `convert_result: bytes` and `set_failure(exc: PdfConversionError)` that clears after one use. Used by all service-layer tests — must be robust.

### T-DOMAIN-07: [x] Add `AuditAction.DOCUMENT_DOWNLOAD` to audit entity
- **Files**: `backend/src/app/domain/entities/audit_log.py`
- **REQs**: REQ-DDF-15
- **Depends on**: —
- **Description**: Add `DOCUMENT_DOWNLOAD = "document.download"` constant. Existing `AuditAction` is a plain class with string constants (not Enum). No migration needed — value stored as string in DB.

### T-DOMAIN-08: [x] Update `Document` entity with dual file fields
- **Files**: `backend/src/app/domain/entities/document.py`
- **REQs**: REQ-DDF-01
- **Depends on**: T-DOMAIN-02
- **Description**: Rename `file_name` → `docx_file_name` and `minio_path` → `docx_minio_path`. Add `pdf_file_name: str | None` and `pdf_minio_path: str | None`. Update all internal references in the entity. Service layer treats PDF fields as required on new rows.

---

## Phase 2 — Infrastructure (DB, deps, docker, adapter)

### T-INFRA-01: [x] Add Gotenberg config to `Settings`
- **Files**: `backend/src/app/config.py`
- **REQs**: REQ-PDF-03
- **Depends on**: —
- **Description**: Add `gotenberg_url: str = "http://gotenberg:3000"` and `gotenberg_timeout: int = 60` to the `Settings` class. Config file is at `backend/src/app/config.py` (NOT `core/config.py`).

### T-INFRA-02: [x] Promote `httpx` and add `respx` dev dep in `pyproject.toml`
- **Files**: `backend/pyproject.toml`
- **REQs**: REQ-PDF-04
- **Depends on**: —
- **Description**: Move `httpx` from `[project.optional-dependencies]` to `[project.dependencies]` pinned `>=0.27.0,<1.0`. Add `respx>=0.20.0,<1.0` to dev/test deps. These are both mechanical edits.

### T-INFRA-03: [x] Update `DocumentModel` SQLAlchemy columns
- **Files**: `backend/src/app/infrastructure/persistence/models/document.py`
- **REQs**: REQ-DDF-01, REQ-DDF-02
- **Depends on**: T-DOMAIN-08
- **Description**: Rename `file_name` → `docx_file_name` (VARCHAR 255) and `minio_path` → `docx_minio_path` (VARCHAR 500) on the SQLAlchemy model. Add `pdf_file_name: Mapped[str | None]` and `pdf_minio_path: Mapped[str | None]` as nullable columns. Must exactly match migration DDL.

### T-INFRA-04: [x] Create Alembic migration `010_pdf_export.py`
- **Files**: `backend/alembic/versions/010_pdf_export.py`
- **REQs**: REQ-DDF-02
- **Depends on**: T-INFRA-03
- **Description**: `upgrade()` renames `file_name→docx_file_name` and `minio_path→docx_minio_path`, adds `pdf_file_name VARCHAR(255) NULL` and `pdf_minio_path VARCHAR(500) NULL`. `downgrade()` reverses all. Set `down_revision = "009"` (verified as latest). No NOT NULL backfill at migration time.

### T-INFRA-05: [x] Add `update_pdf_fields` method to `DocumentRepository`
- **Files**: `backend/src/app/infrastructure/persistence/repositories/document_repository.py`
- **REQs**: REQ-DDF-09
- **Depends on**: T-INFRA-03
- **Description**: Add `async def update_pdf_fields(self, doc_id: UUID, pdf_file_name: str, pdf_minio_path: str) -> Document` that issues a single UPDATE and returns the updated entity. Used exclusively by `ensure_pdf`.

### T-INFRA-06: [x] [TEST] Adapter unit tests for `GotenbergPdfConverter`
- **Files**: `backend/tests/unit/infrastructure/test_gotenberg_pdf_converter.py`
- **REQs**: REQ-PDF-02, REQ-PDF-08, REQ-PDF-09, SCEN-PDF-01..05
- **Depends on**: T-DOMAIN-04, T-INFRA-01, T-INFRA-02
- **Description**: Use `respx` to mock `httpx`. Cover: 2xx → returns bytes (SCEN-PDF-01); 5xx → `PdfConversionError` with status ref (SCEN-PDF-02); connection refused via `httpx.ConnectError` → `PdfConversionError` (SCEN-PDF-03); timeout via `httpx.TimeoutException` → `PdfConversionError` (SCEN-PDF-04); empty input `b""` → `PdfConversionError` before HTTP call (SCEN-PDF-05). Also verify INFO log on success and ERROR log on failure.

### T-INFRA-07: [x] Implement `GotenbergPdfConverter` adapter
- **Files**: `backend/src/app/infrastructure/pdf/__init__.py`, `backend/src/app/infrastructure/pdf/gotenberg_pdf_converter.py`
- **REQs**: REQ-PDF-02, REQ-PDF-08, REQ-PDF-09, REQ-PDF-10
- **Depends on**: T-INFRA-06
- **Description**: Implements `PdfConverter` using `httpx.AsyncClient` (natively async — no `asyncio.to_thread`). POST multipart to `{gotenberg_url}/forms/libreoffice/convert`; field name `files`, `filename="document.docx"`, correct MIME type. Wraps ALL httpx errors and non-2xx into `PdfConversionError`. Logs duration (ms) via existing app logger. `__init__.py` provides `@lru_cache get_pdf_converter()` factory.

### T-INFRA-08: [x] Add `gotenberg` service to `docker-compose.yml`
- **Files**: `docker/docker-compose.yml`
- **REQs**: REQ-PDF-05
- **Depends on**: T-INFRA-01
- **Description**: Add `gotenberg` service using image `gotenberg/gotenberg:8.16` (pinned minor, not `:8`), internal port 3000, healthcheck `curl -f http://localhost:3000/health`, connected to `sigdoc` network. Set `api: depends_on: gotenberg: condition: service_healthy`. Do NOT expose a host port.

---

## Phase 3 — Application service layer (orchestration)

### T-APP-01: [x] [TEST] Unit tests for atomic dual-format generation
- **Files**: `backend/tests/unit/test_document_service_pdf.py`
- **REQs**: REQ-DDF-03, REQ-DDF-05, REQ-DDF-14, REQ-DDF-16, SCEN-DDF-05, SCEN-DDF-15
- **Depends on**: T-DOMAIN-06, T-DOMAIN-07, T-DOMAIN-08
- **Description**: Using `FakePdfConverter` + `FakeStorageService` + `FakeDocumentRepository`: assert both files in MinIO + row with dual fields on success; assert DOCX deleted from MinIO + no DB row when `PdfConverter.convert()` raises (SCEN-DDF-05); assert `details.formats_generated=["docx","pdf"]` in audit event; assert quota incremented by exactly 1.

### T-APP-02: [x] Modify `DocumentService.generate` for atomic dual-format flow
- **Files**: `backend/src/app/application/services/document_service.py`
- **REQs**: REQ-DDF-03, REQ-DDF-05, REQ-DDF-14, REQ-DDF-16
- **Depends on**: T-APP-01, T-DOMAIN-08, T-INFRA-07
- **Description**: After DOCX upload, call `await self._pdf_converter.convert(rendered_docx)`. On `PdfConversionError`: delete orphan DOCX from MinIO and re-raise (presentation maps → 503). On success: upload PDF, persist `Document` with all four file fields. Update audit details with `formats_generated=["docx","pdf"]`. Quota increment unchanged (still +1).

### T-APP-03: [x] [TEST] Unit tests for atomic bulk dual-format generation
- **Files**: `backend/tests/unit/test_document_service_pdf.py`
- **REQs**: REQ-DDF-04, REQ-DDF-05, SCEN-DDF-05
- **Depends on**: T-APP-01
- **Description**: Assert that when any row's conversion fails, ALL previously uploaded DOCX and PDF objects for this batch are deleted from MinIO and no `Document` rows persist. Use `FakePdfConverter` with `set_failure()` on the Nth call.

### T-APP-04: [x] Modify `DocumentService.generate_bulk` for dual-format flow
- **Files**: `backend/src/app/application/services/document_service.py`
- **REQs**: REQ-DDF-04, REQ-DDF-05
- **Depends on**: T-APP-03, T-APP-02
- **Description**: Apply the same atomic dual-format logic per row as T-APP-02. Sequential processing. Track all uploaded MinIO keys for the batch. On any `PdfConversionError`: delete ALL accumulated MinIO objects (DOCX + PDF for all rows processed so far), raise without persisting any rows.

### T-APP-05: [x] [TEST] Unit tests for `ensure_pdf` lazy backfill
- **Files**: `backend/tests/unit/test_document_service_pdf.py`
- **REQs**: REQ-DDF-09, REQ-DDF-10, SCEN-DDF-06, SCEN-DDF-07
- **Depends on**: T-INFRA-05, T-DOMAIN-06
- **Description**: Assert happy path: `pdf_file_name IS NULL` → convert → upload → `update_pdf_fields` called → returns updated doc; idempotent path: `pdf_file_name` already set → returns doc immediately without conversion; failure path: `PdfConversionError` raised → `update_pdf_fields` never called, DOCX not deleted.

### T-APP-06: [x] Implement `DocumentService.ensure_pdf`
- **Files**: `backend/src/app/application/services/document_service.py`
- **REQs**: REQ-DDF-09, REQ-DDF-10
- **Depends on**: T-APP-05, T-INFRA-05
- **Description**: New async method `ensure_pdf(document_id: UUID) -> Document`. Fast path returns immediately if `pdf_file_name is not None`. Slow path: download DOCX bytes from MinIO → convert → upload PDF → call `doc_repo.update_pdf_fields()` → return updated doc. On `PdfConversionError`: do NOT delete DOCX, do NOT update DB, let exception propagate (presentation maps → 503).

### T-APP-07: [x] Wire `PdfConverter` into DI / `DocumentService` factory
- **Files**: `backend/src/app/application/services/__init__.py`
- **REQs**: REQ-PDF-02
- **Depends on**: T-INFRA-07, T-APP-06
- **Description**: Inject `PdfConverter` (via `get_pdf_converter()` factory from `infrastructure/pdf/__init__.py`) into `DocumentService` constructor. Update whatever factory function / `get_document_service()` the DI container uses to pass the new dependency.

---

## Phase 4 — Presentation (endpoints + RBAC + audit)

### T-PRES-01: [x] Remove `output_format` from generate request schema
- **Files**: `backend/src/app/presentation/schemas/document.py`
- **REQs**: REQ-DDF-03, REQ-DDF-04, SCEN-DDF-04
- **Depends on**: T-APP-02
- **Description**: Drop `output_format` field from `GenerateDocumentRequest` (and bulk equivalent if separate). Pydantic will reject unknown fields → 422 automatically if `model_config = ConfigDict(extra="forbid")`. Verify and enable `extra="forbid"` if not already set.

### T-PRES-02: [x] [TEST] Endpoint tests for single-doc download RBAC
- **Files**: `backend/tests/integration/test_documents_api.py`
- **REQs**: REQ-DDF-06, REQ-DDF-07, REQ-DDF-15, SCEN-DDF-01..03
- **Depends on**: T-APP-06, T-DOMAIN-02
- **Description**: Test: format=docx admin → 200 + correct MIME (SCEN-DDF-01); format=pdf non-admin → 200 + PDF bytes + audit event with `via="direct"` (SCEN-DDF-02); format=docx non-admin → 403 non-leaky message (SCEN-DDF-03); missing format → 422.

### T-PRES-03: [x] Modify single-doc download endpoint
- **Files**: `backend/src/app/presentation/api/v1/documents.py`
- **REQs**: REQ-DDF-06, REQ-DDF-07, REQ-DDF-09, REQ-DDF-13, REQ-DDF-15
- **Depends on**: T-PRES-02, T-APP-06, T-DOMAIN-02, T-DOMAIN-07
- **Description**: Add `format: Literal["pdf","docx"] = Query(...)` and `via: Literal["direct","share"] = Query("direct")` params to `GET /documents/{id}/download`. Call `can_download_format(current_user.role, format)` → 403 on False. For PDF: call `ensure_pdf(id)` (handles legacy backfill transparently). Write `DOCUMENT_DOWNLOAD` audit event with `{format, document_id, via}` on success.

### T-PRES-04: [x] [TEST] Endpoint tests for bulk download RBAC
- **Files**: `backend/tests/integration/test_documents_api.py`
- **REQs**: REQ-DDF-11, REQ-DDF-12, SCEN-DDF-09..12
- **Depends on**: T-PRES-02
- **Description**: Test: admin format=pdf → 200 ZIP with .pdf files (SCEN-DDF-09); admin include_both=true → 200 ZIP with .docx + .pdf per row (SCEN-DDF-10); non-admin format=docx → 403 (SCEN-DDF-11); non-admin include_both=true → 403 (SCEN-DDF-12); missing format → 422.

### T-PRES-05: [x] Modify bulk download endpoint
- **Files**: `backend/src/app/presentation/api/v1/documents.py`
- **REQs**: REQ-DDF-11, REQ-DDF-12, REQ-DDF-15
- **Depends on**: T-PRES-04, T-APP-06, T-DOMAIN-02
- **Description**: Add `format: Literal["pdf","docx"] = Query(...)` and `include_both: bool = Query(False)` to bulk download. RBAC: non-admin + format=docx → 403; non-admin + include_both=true → 403. Serial `ensure_pdf()` for legacy rows in batch when format includes PDF. Build ZIP per ADR-PDF-08. Write `DOCUMENT_DOWNLOAD` audit event per file or per batch (single event with list is acceptable).

### T-PRES-06: [x] [TEST] Endpoint tests for `output_format` rejection and sharing RBAC
- **Files**: `backend/tests/integration/test_documents_api.py`
- **REQs**: REQ-DDF-03, REQ-DDF-13, SCEN-DDF-04, SCEN-DDF-13, SCEN-DDF-14
- **Depends on**: T-PRES-03
- **Description**: Test: POST /generate with `output_format` in body → 422 (SCEN-DDF-04); non-admin via share-link calls download?format=docx → 403 (SCEN-DDF-13); non-admin via share-link calls download?format=pdf&via=share → 200 + audit `via="share"` (SCEN-DDF-14).

### T-PRES-07: [x] Add `via=share` sanity check in download endpoint
- **Files**: `backend/src/app/presentation/api/v1/documents.py`
- **REQs**: REQ-DDF-15
- **Depends on**: T-PRES-06, T-PRES-03
- **Description**: If `via=share` is passed but `current_user` is the document creator AND template is not shared, override `via` to `"direct"` before writing the audit event (ADR-PDF-07). This preserves audit integrity against client lying about `via`.

---

## Phase 5 — Frontend

### T-FE-01: [x] Install `dropdown-menu` shadcn primitive
- **Files**: `frontend/src/components/ui/dropdown-menu.tsx`
- **REQs**: REQ-DDF-17
- **Depends on**: —
- **Description**: Run `npx shadcn-ui@latest add dropdown-menu` in `frontend/`. This generates `components/ui/dropdown-menu.tsx` using Radix UI (keyboard accessible by default). Commit the generated file without manual edits.

### T-FE-02: [x] Update API client download URL builder
- **Files**: `frontend/src/features/documents/api/queries.ts`
- **REQs**: REQ-DDF-06, REQ-DDF-15
- **Depends on**: —
- **Description**: Update download URL builder to include `format=pdf|docx` query param and optional `via=direct|share` param. All existing callers will be updated in T-FE-04/T-FE-05.

### T-FE-03: [x] Remove `output_format` from generate mutations
- **Files**: `frontend/src/features/documents/api/mutations.ts`
- **REQs**: REQ-DDF-03, REQ-DDF-04
- **Depends on**: —
- **Description**: Remove `output_format` from the generate and generate-bulk request payloads. The field must be absent (not null/undefined) from the serialized body. Update TypeScript types accordingly.

### T-FE-04: [x] Create `DownloadButton` role-aware component
- **Files**: `frontend/src/features/documents/components/DownloadButton.tsx`
- **REQs**: REQ-DDF-17
- **Depends on**: T-FE-01, T-FE-02
- **Description**: Admin renders `DropdownMenu` with "Descargar como PDF" and "Descargar como Word" items. Non-admin renders a single `<Button>` "Descargar PDF" with no caret (Word option NOT in DOM). Role derived from `useAuth().user.role`. Accepts `documentId` and `via?: "direct"|"share"` props.

### T-FE-05: [x] Replace download triggers in `DynamicForm.tsx` and `DocumentList.tsx`
- **Files**: `frontend/src/features/documents/components/DynamicForm.tsx`, `frontend/src/features/documents/components/DocumentList.tsx`
- **REQs**: REQ-DDF-17
- **Depends on**: T-FE-04
- **Description**: Replace existing download button/action in both files with `<DownloadButton documentId={...} via="direct" />`. Verify no other files in the `documents/` feature contain a download trigger that bypasses the new component.

### T-FE-06: [x] Update `BulkGenerateFlow.tsx` with bulk download controls
- **Files**: `frontend/src/features/documents/components/BulkGenerateFlow.tsx`
- **REQs**: REQ-DDF-18
- **Depends on**: T-FE-04, T-FE-02
- **Description**: Add admin-only `include_both` checkbox ("Incluir documentos Word") — rendered ONLY when `user.role === "admin"`, NOT just disabled. Wire checkbox state as `include_both` query param on the bulk download request. Replace existing bulk download trigger with `<DownloadButton>` for consistency.

---

## Phase 6 — Integration tests + smoke

### T-INT-01: [x] [TEST] E2E happy path — admin generates, both files in MinIO, downloads both formats
- **Files**: `backend/tests/integration/test_pdf_export.py`
- **REQs**: REQ-DDF-01, REQ-DDF-03, REQ-DDF-19, SCEN-DDF-01
- **Depends on**: T-PRES-03, T-PRES-05
- **Description**: Admin POST /generate → assert response 200 + `Document` row has both `docx_file_name` and `pdf_file_name` populated. Admin GET /download?format=docx → 200 + DOCX MIME. Non-admin GET /download?format=pdf → 200 + PDF MIME. Full stack with FastAPI TestClient.

### T-INT-02: [x] [TEST] E2E legacy backfill — pre-existing DOCX-only doc → user PDF request → PDF persisted → second request skips conversion
- **Files**: `backend/tests/integration/test_pdf_export.py`
- **REQs**: REQ-DDF-09, REQ-DDF-10, SCEN-DDF-06, SCEN-DDF-07
- **Depends on**: T-PRES-03
- **Description**: Insert legacy `Document` row (manually, `pdf_file_name=None`). Non-admin GET /download?format=pdf → 200 → assert `pdf_file_name` now set in DB. Repeat GET → same 200 without re-triggering conversion (verify via mock call count). Also: simulate Gotenberg failure → 503 → `pdf_file_name` still NULL.

### T-INT-03: [x] [TEST] Sharing RBAC — recipient non-admin cannot download DOCX via share link
- **Files**: `backend/tests/integration/test_pdf_export.py`
- **REQs**: REQ-DDF-13, SCEN-DDF-13, SCEN-DDF-14
- **Depends on**: T-PRES-07
- **Description**: Admin shares template with non-admin; non-admin generates document via share. Non-admin GET /download?format=docx → 403. Non-admin GET /download?format=pdf&via=share → 200 + audit event has `via="share"`.

### T-INT-04: [x] [TEST] Migration regression — existing rows have `docx_file_name` populated, `pdf_file_name` NULL
- **Files**: `backend/tests/integration/test_pdf_export.py`
- **REQs**: REQ-DDF-02
- **Depends on**: T-INFRA-04
- **Description**: Run migration `010_pdf_export` against a test DB with a pre-existing `Document` row. Assert: `docx_file_name` = original `file_name` value; `docx_minio_path` = original `minio_path` value; `pdf_file_name IS NULL`; `pdf_minio_path IS NULL`. Downgrade → assert columns back to original names.

### T-INT-05: [x] [TEST] Quota — single generate increments by exactly 1
- **Files**: `backend/tests/integration/test_pdf_export.py`
- **REQs**: REQ-DDF-16, SCEN-DDF-15
- **Depends on**: T-APP-02
- **Description**: Record quota counter before POST /generate. After successful response, assert counter incremented by exactly 1 (not 2). Also assert audit event contains `details.formats_generated=["docx","pdf"]`.

### T-INT-06: [x] Run full backend test suite — no regressions
- **Files**: (no new files — validation task)
- **REQs**: all
- **Depends on**: T-INT-01, T-INT-02, T-INT-03, T-INT-04, T-INT-05
- **Description**: Run `pytest backend/` and assert all existing tests still pass. This is the regression gate before Phase 7. Target: 0 new failures in the existing suite.

---

## Phase 7 — Operational / pre-flight (not code — required before merging)

### T-OPS-01: Verify nginx upstream timeout for bulk download path
- **Files**: (config/infra — not a Python file)
- **REQs**: ADR-PDF-08 (design risk)
- **Depends on**: T-PRES-05
- **Description**: Confirm nginx `proxy_read_timeout` (or equivalent) is ≥ 300s on the `/documents/bulk/*/download` path. Worst-case latency is ~150s for 50 legacy rows; 300s gives 2× headroom. Document the finding and update nginx config if needed.

### T-OPS-02: Update `.env.example` with Gotenberg vars
- **Files**: `.env.example` (project root or `backend/`)
- **REQs**: REQ-PDF-03
- **Depends on**: T-INFRA-01
- **Description**: Add `GOTENBERG_URL=http://gotenberg:3000` and `GOTENBERG_TIMEOUT=60` with comments. Also verify `README` or dev-setup docs mention the new `gotenberg` service in `docker compose up`.

### T-OPS-03: Pin Gotenberg image to exact minor version
- **Files**: `docker/docker-compose.yml`
- **REQs**: REQ-PDF-05
- **Depends on**: T-INFRA-08
- **Description**: Confirm the image tag in docker-compose is `:8.16` (or latest `:8.x` minor at merge time) — NOT just `:8`. Record the pinned version in a comment. This prevents silent drift across environments.

---

## Estimate

| Phase | Tasks | ~Hours |
|-------|-------|--------|
| Phase 1 — Domain & permissions | 8 | 3 h |
| Phase 2 — Infrastructure | 8 | 4 h |
| Phase 3 — Application service | 7 | 4 h |
| Phase 4 — Presentation | 7 | 4 h |
| Phase 5 — Frontend | 6 | 3 h |
| Phase 6 — Integration tests | 6 | 3 h |
| Phase 7 — Operational | 3 | 1 h |
| **Total** | **45** | **~22 h** |

*(Estimate is informational, not a contract. Hours assume Strict TDD mode — tests before implementation adds ~30 % overhead but reduces debugging time.)*
