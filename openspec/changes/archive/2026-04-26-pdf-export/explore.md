# Exploration: PDF Export via Gotenberg

## Goal

Add the ability to download generated documents as PDF in addition to the current DOCX format, using Gotenberg as a sidecar Docker service for DOCX→PDF conversion.

---

## Current State

### DOCX Generation Pipeline (end-to-end)

**Port layer:**
- `backend/src/app/domain/ports/template_engine.py:4` — `TemplateEngine` ABC with `extract_variables`, `render`, `validate`, `auto_fix`. Output of `render()` is raw `bytes` (DOCX).
- `backend/src/app/domain/ports/storage_service.py:4` — `StorageService` ABC with `upload_file`, `download_file`, `get_presigned_url`, `delete_file`.
- No `PdfConverter` port exists yet.

**Infrastructure:**
- `backend/src/app/infrastructure/templating/docxtpl_engine.py:60` — `DocxTemplateEngine` renders via `DocxTemplate`, writes to `BytesIO`, returns DOCX bytes.
- `backend/src/app/infrastructure/storage/minio_storage.py:18` — `MinioStorageService` wraps the synchronous `minio` SDK via `asyncio.to_thread()`. No HTTP client used here.
- Adapter instantiation pattern: `backend/src/app/infrastructure/storage/__init__.py:7` — `@lru_cache` factory `get_storage_service()` returns singleton. Same pattern in `infrastructure/templating/__init__.py:7`.

**Application layer:**
- `backend/src/app/application/services/document_service.py:56` — `generate_single()` pipeline:
  1. Quota check (optional)
  2. Fetch template version from DB
  3. Access check
  4. `storage.download_file(templates bucket, version.minio_path)` → DOCX bytes
  5. `engine.render(template_bytes, variables)` → rendered DOCX bytes
  6. `storage.upload_file(documents bucket, path)` — persisted with `.docx` extension
  7. `doc_repo.create(Document(...))` — DB record with `minio_path` and `file_name`
  8. `usage_service.record()` + `audit_service.log()` (both optional)
  9. Return `{document, download_url}` where download_url is presigned MinIO URL
- `backend/src/app/application/services/document_service.py:382` — `generate_bulk()`:
  - Renders N documents in-process, packs into ZIP via `zipfile.ZipFile`
  - Uploads `bulk.zip` to MinIO
  - All DOCX only — no PDF path exists

**DI / service factory:**
- `backend/src/app/application/services/__init__.py` — `get_document_service()` constructs `DocumentService` with `storage=get_storage_service()`, `engine=get_template_engine()`. New `pdf_converter` would be injected here.

**Config:**
- `backend/src/app/config.py:6` — `Settings` (pydantic-settings). No Gotenberg URL yet. Pattern is simple `str` fields like `minio_endpoint: str = "minio:9000"` — adding `gotenberg_url: str = "http://gotenberg:3000"` fits naturally.

**API layer:**
- `backend/src/app/presentation/api/v1/documents.py:54` — `POST /generate` → calls `service.generate_single()` → returns `DocumentResponse` with `download_url` pointing to `/documents/{id}/download`
- `backend/src/app/presentation/api/v1/documents.py:193` — `GET /{document_id}/download` → fetches from MinIO, returns `Response` with `application/vnd.openxmlformats-officedocument.wordprocessingml.document` MIME type
- `backend/src/app/presentation/api/v1/documents.py:116` — `POST /generate-bulk` → returns `BulkGenerateResponse` with `download_url` pointing to `/documents/bulk/{batch_id}/download`

**Frontend download flow:**
- `frontend/src/features/documents/components/DynamicForm.tsx:69` — `handleDownload()` calls `GET /documents/{documentId}/download` with `responseType: "blob"`, creates a temporary `<a>` element, triggers browser download with the file name from the generate response.
- `frontend/src/features/documents/components/BulkGenerateFlow.tsx:101` — same blob download pattern for ZIP.
- No format selection UI exists today.

**Rate limiting:**
- `backend/src/app/presentation/api/v1/documents.py:55` — `@limiter.limit(tier_limit_generate)` on generate; `@limiter.limit(tier_limit_bulk)` on bulk.
- `backend/src/app/presentation/middleware/rate_limit.py:91` — `tier_limit_generate()` and `tier_limit_bulk()` read from `SubscriptionTier.rate_limit_generate` and `rate_limit_bulk` via ContextVar. PDF generation is effectively a document generation action — it should share the same `tier_limit_generate` and `tier_limit_bulk` rate limits.

**Audit:**
- `backend/src/app/domain/entities/audit_log.py:12` — `AuditAction.DOCUMENT_GENERATE = "document.generate"` and `DOCUMENT_GENERATE_BULK = "document.generate_bulk"`.
- Audit log `details` field (`dict | None`) accepts arbitrary extra keys — adding `"format": "pdf"` to details is backward-compatible with no schema migration.

**Quota / subscription:**
- `backend/src/app/application/services/quota_service.py:74` — `check_document_quota()` counts against `monthly_document_limit`. PDF generation IS a document generation — it should count against the same quota. No separate PDF tier field exists or is needed.
- `backend/src/app/domain/entities/subscription_tier.py:13` — `SubscriptionTier` has no PDF-specific field. Deliberate.

**HTTP client:**
- `backend/pyproject.toml` — `httpx>=0.27.0` is already a **dev dependency** (used in tests). It is NOT in the production dependency list directly — but it's listed under `[project.optional-dependencies] dev`. The production code currently uses `minio` SDK (which uses `urllib3` internally) and `aiosmtplib` for email. **`httpx` would need to be promoted to a production dependency** to call Gotenberg from the service layer. Cost: minimal — httpx is already pinned and tested.

**Docker Compose:**
- `docker/docker-compose.yml` — services: `db`, `minio`, `minio-init`, `api`, `nginx`. All share the `sigdoc` bridge network. Pattern for new sidecar services is clear: add a new service with `image`, `healthcheck`, and `networks: - sigdoc`.
- Gotenberg uses `image: gotenberg/gotenberg:8`, exposes port 3000. No volumes needed (stateless conversion). Healthcheck: `GET /health` returns 200.
- Memory: `gotenberg/gotenberg:8` bundles LibreOffice (~250 MB image, ~150–300 MB RAM at runtime per active conversion). This is the main operational cost.

**Test fakes:**
- `backend/tests/fakes/fake_template_engine.py` — `FakeTemplateEngine(TemplateEngine)`: stores configurable state (`render_result`, `should_fail`), `async` methods.
- `backend/tests/fakes/fake_storage_service.py` — `FakeStorageService(StorageService)`: `dict[(bucket, path)] → bytes` in-memory store.
- New `FakePdfConverter` would follow the same pattern: configurable `convert_result: bytes`, `should_fail: bool`.

**Document entity:**
- `backend/src/app/domain/entities/document.py:7` — `Document` dataclass has `file_name: str` and `minio_path: str` but no `format` field. Adding a `format: str = "docx"` field would require a DB migration. Alternative: derive format from `file_name` extension.

**Email sharing:**
- `backend/src/app/domain/ports/email_service.py:10` — `EmailService.send_email(to, subject, html_body, text_body)`. The share-by-email flow sends a link; it does not attach the document. PDF export does not directly affect email sharing unless a future feature attaches PDFs — that is out of scope for this change.

---

## Proposed Direction

### New port: `PdfConverter`

```
backend/src/app/domain/ports/pdf_converter.py
```

```python
class PdfConverter(ABC):
    @abstractmethod
    async def convert(self, docx_bytes: bytes) -> bytes:
        """Convert DOCX bytes to PDF bytes. Raises PdfConversionError on failure."""
        ...
```

### New adapter: `GotenbergPdfConverter`

```
backend/src/app/infrastructure/pdf/gotenberg_pdf_converter.py
```

- Uses `httpx.AsyncClient` (already pinned, to be promoted to prod dep)
- POSTs the DOCX to `{GOTENBERG_URL}/forms/libreoffice/convert`
- Returns raw PDF bytes
- Raises `PdfConversionError` (new domain exception) if Gotenberg returns non-2xx

### New factory:

```
backend/src/app/infrastructure/pdf/__init__.py
```

Same `@lru_cache` + `get_pdf_converter()` pattern.

### Config addition:

```python
# backend/src/app/config.py
gotenberg_url: str = "http://gotenberg:3000"
```

### DocumentService changes:

`generate_single()` and `generate_bulk()` gain an optional `output_format: Literal["docx", "pdf"] = "docx"` parameter. When `pdf`:
1. Render to DOCX bytes (existing step)
2. Call `self._pdf_converter.convert(rendered_bytes)` → PDF bytes
3. Upload PDF to MinIO with `.pdf` extension and `application/pdf` content type
4. Set `file_name` with `.pdf` extension
5. Audit log gets `details={"format": "pdf"}` added

For bulk PDF: the ZIP contains `.pdf` files instead of `.docx` files.

### API changes:

- `POST /documents/generate` gains optional `output_format: "docx" | "pdf"` field in `GenerateRequest`
- `GET /{document_id}/download` derives Content-Type from `file_name` extension (already flexible via `Response`)
- `POST /documents/generate-bulk` gains optional `output_format` form field

### Frontend changes:

- `DynamicForm.tsx` gains a format toggle ("Descargar como DOCX / PDF") before the submit button
- `BulkGenerateFlow.tsx` gains the same toggle in Step 1 or 3

### Docker Compose addition:

```yaml
gotenberg:
  image: gotenberg/gotenberg:8
  command: gotenberg --chromium-disable-javascript=true --chromium-allow-list=file:///tmp/.*
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
    interval: 10s
    retries: 5
  networks:
    - sigdoc

api:
  depends_on:
    gotenberg:
      condition: service_healthy
```

---

## Tradeoffs

| Approach | Pros | Cons | Verdict |
|---|---|---|---|
| **Gotenberg (separate service)** | API container stays lean (no LibreOffice); scales independently (multiple Gotenberg replicas possible); battle-tested in production; stateless HTTP API is easy to fake in tests; httpx already pinned | +250 MB image pull; +150–300 MB RAM at runtime; adds a network hop (~50–200ms latency per conversion); dev setup requires running one more container; httpx must be promoted from dev to prod dep | **Recommended** |
| **LibreOffice embedded in `api` container** | No extra container; single Dockerfile; zero network latency for conversion | Bloats api image by ~400–600 MB; LibreOffice subprocess model does not play well with asyncio (needs `asyncio.to_thread` + temp files + process pool); version drift between LibreOffice and docx template format; harder to scale (every api replica carries LibreOffice) | Reject |
| **WeasyPrint (HTML→PDF after DOCX→HTML)** | Pure Python (pip install); no extra container; actively maintained | DOCX→HTML conversion is lossy (tables, images, fonts, headers/footers break); WeasyPrint does HTML→PDF, not DOCX→PDF — needs an intermediate converter; output quality typically unacceptable for document-generation use case | Reject |

---

## Open Questions for Proposal Phase

1. **PDF on demand or persisted?** The current design persists DOCX to MinIO immediately. For PDF, should we persist it alongside (two MinIO objects per doc), generate on demand from the stored DOCX each download, or only when the user explicitly requests PDF format? Recommended: generate at request time and persist (same as DOCX) to avoid re-conversion on re-download.

2. **Bulk PDF = ZIP of PDFs?** The current bulk path produces a `bulk.zip` of DOCX files. Should PDF bulk produce a ZIP of PDFs? Answer is almost certainly yes — but this needs a decision on whether the single `generate_bulk()` method handles it, or if there's a separate endpoint.

3. **Same audit event or new?** Current audit actions are `document.generate` and `document.generate_bulk`. Options: (a) extend existing events with `details.format = "pdf"` — backward-compatible, no new AuditAction constant; (b) add `DOCUMENT_GENERATE_PDF = "document.generate_pdf"` — cleaner filtering but breaks existing audit queries. Recommended: option (a) — add `format` to `details` dict, no new action type.

4. **Document entity `format` field?** Currently `Document.file_name` carries the extension. Should we add an explicit `format: str = "docx"` field to the `Document` entity? This would require an Alembic migration. Pro: explicit; Con: `file_name` already carries the info. Decision deferred to proposal/spec.

5. **Rate limiting for PDF?** PDF generation is slower than DOCX (Gotenberg conversion adds ~1–5s). Should `tier_limit_generate` apply to PDF the same as DOCX, or should PDF have a tighter limit? Current tier field is `rate_limit_generate: str`. Simplest: reuse same limit (PDF and DOCX share the counter). A separate `rate_limit_generate_pdf` field would require a DB migration and tier re-seeding.

6. **Gotenberg timeout?** LibreOffice conversion of large/complex DOCX can take 5–30 seconds. The httpx client call needs an explicit timeout; the default FastAPI request timeout may also need adjustment. Recommended: `httpx.AsyncClient(timeout=60.0)` for Gotenberg calls.

7. **Email sharing + PDF?** The current share-by-email flow sends a link, not an attachment. PDF export does not affect this flow. If a future request adds "attach PDF to email", that's a separate change.

---

## Risks

1. **Gotenberg availability** — If the Gotenberg container is down, PDF generation fails. The API should return 503 (not 500) and surface a clear error to the frontend. DOCX generation is unaffected (independent path).

2. **Conversion fidelity** — LibreOffice rendering of complex DOCX templates (tables, images, custom fonts) may produce imperfect PDFs. This is an inherent limitation of the approach, not a code defect. Should be documented.

3. **Memory spikes on bulk PDF** — Converting 50 DOCX files serially in `generate_bulk()` calls Gotenberg 50 times. Each call runs LibreOffice, which can spike to 200–400 MB RAM. Under load, concurrent bulk PDF requests could exhaust Gotenberg's memory. Mitigation: keep the existing `bulk_generation_limit` (enforced by `QuotaService.check_bulk_limit()`); consider sequential (not concurrent) Gotenberg calls in bulk.

4. **httpx promotion** — `httpx` must be moved from `[project.optional-dependencies] dev` to `[project.dependencies]` in `pyproject.toml`. This is trivial but must not be forgotten.

5. **Cold start latency** — LibreOffice inside Gotenberg has a ~1–3 second warm-up on first conversion. Subsequent conversions are faster (LibreOffice stays resident). In low-traffic environments this is noticeable. Mitigation: Gotenberg can be pinged on startup (health check dependency in compose) — LibreOffice warms up on first real request.

6. **No existing `PdfConversionError`** — needs to be added to `backend/src/app/domain/exceptions.py`. The API layer maps it to HTTP 502 (upstream conversion failed) or 503 (Gotenberg unavailable).

---

## Files Read

| File | What was learned |
|---|---|
| `backend/src/app/domain/ports/template_engine.py` | `TemplateEngine` port — `render()` returns `bytes`; port pattern uses ABC with abstract async methods |
| `backend/src/app/domain/ports/storage_service.py` | `StorageService` port — upload/download/presign/delete; same ABC pattern |
| `backend/src/app/application/services/document_service.py` | Full single and bulk generation pipeline; how usage + audit are called; where a `pdf_converter` dependency would be injected |
| `backend/src/app/presentation/api/v1/documents.py` | `/generate`, `/generate-bulk`, `/{id}/download`, `/bulk/{batch_id}/download` endpoints; rate limit decorators applied |
| `backend/src/app/infrastructure/templating/docxtpl_engine.py` | `DocxTemplateEngine` — uses `asyncio.to_thread`; fresh `DocxTemplate` per render; temp file pattern |
| `backend/src/app/infrastructure/storage/minio_storage.py` | `MinioStorageService` — sync SDK wrapped with `to_thread`; no httpx used here |
| `backend/src/app/infrastructure/storage/__init__.py` | `@lru_cache` factory pattern for infrastructure adapters |
| `backend/src/app/infrastructure/templating/__init__.py` | Same `@lru_cache` factory pattern |
| `backend/src/app/application/services/__init__.py` | `get_document_service()` DI factory — where `pdf_converter` will be injected |
| `backend/src/app/config.py` | `Settings` via pydantic-settings; `gotenberg_url` config field would fit naturally |
| `backend/src/app/domain/entities/document.py` | `Document` dataclass — no `format` field; `file_name` carries extension |
| `backend/src/app/domain/entities/audit_log.py` | `AuditAction` constants; `details: dict | None` is extension point |
| `backend/src/app/domain/entities/subscription_tier.py` | `SubscriptionTier` — `rate_limit_generate`, `rate_limit_bulk` fields; no PDF-specific field |
| `backend/src/app/application/services/quota_service.py` | `check_document_quota()` counts docs against `monthly_document_limit`; PDF shares same quota |
| `backend/src/app/presentation/middleware/rate_limit.py` | `tier_limit_generate()` and `tier_limit_bulk()` — zero-arg callables reading ContextVar |
| `backend/pyproject.toml` | `httpx>=0.27.0` is dev-only dependency — needs promotion to prod |
| `backend/tests/fakes/fake_template_engine.py` | Fake pattern: inherit port ABC, configurable fields, async methods |
| `backend/tests/fakes/fake_storage_service.py` | Fake pattern: in-memory `dict[(bucket, path)] → bytes` |
| `docker/docker-compose.yml` | Services + `sigdoc` bridge network; healthcheck patterns; where Gotenberg service would go |
| `docker/Dockerfile.backend` | `python:3.12-slim`; installs deps from pyproject.toml; no LibreOffice |
| `frontend/src/features/documents/components/DynamicForm.tsx` | `handleDownload()` — blob download from `/documents/{id}/download`; format toggle would go before submit button |
| `frontend/src/features/documents/components/BulkGenerateFlow.tsx` | 4-step bulk flow; ZIP download at step 4; format toggle would go at step 1 or 3 |
| `frontend/src/features/documents/api/mutations.ts` | `useGenerateDocument()`, `useBulkGenerate()` mutations — `GenerateRequest` type needs `output_format` field |
