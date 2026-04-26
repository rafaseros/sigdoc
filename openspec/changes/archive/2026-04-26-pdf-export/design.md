# Design: PDF Export via Gotenberg (with role-gated download)

**Change ID:** `pdf-export`

## Technical Approach

Introduce a hexagonal `PdfConverter` port + `GotenbergPdfConverter` async adapter. `DocumentService.generate_*` becomes a transactional, atomic dual-format flow (DOCX + PDF or nothing). A new domain module `document_permissions.py` owns the role-vs-format decision; both download endpoints route through it. Legacy rows are PDF-backfilled lazily inside the service. Migration `010_pdf_export.py` renames the existing single-format columns and adds nullable PDF columns.

## Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Presentation                                                            │
│  ─────────────────────────────────────────────────────────────────────  │
│  documents.py [MODIFIED]                                                 │
│    POST /generate              ── no output_format  ──┐                 │
│    POST /generate-bulk         ── no output_format  ──┤                 │
│    GET  /{id}/download?format=…&via=…  [MODIFIED]   ──┤                 │
│    GET  /bulk/{id}/download?format=…&include_both=… ──┤                 │
└──────────────────────────────────────────────────────┬────────────────────┘
                                                       │
┌──────────────────────────────────────────────────────▼─────────────────┐
│  Application                                                            │
│  ──────────────────────────────────────────────────────────────────── │
│  DocumentService [MODIFIED]                                             │
│    generate_single → render → upload DOCX → convert → upload PDF →     │
│                      persist → audit  (atomic; cleanup on PDF fail)    │
│    generate_bulk   → same per row, sequential, fail-batch on any error │
│    ensure_pdf      [NEW] lazy backfill — convert + persist if NULL     │
│                                                                         │
│    Audit: DOCUMENT_GENERATE.details.formats_generated = ["docx","pdf"] │
│    Audit: DOCUMENT_DOWNLOAD.details = {format, document_id, via}       │
└────────────┬──────────────────────────────────┬─────────────────────────┘
             │                                  │
┌────────────▼─────────────┐    ┌───────────────▼───────────────────────┐
│  Domain                  │    │  Infrastructure                        │
│  ────────────────        │    │  ──────────────────────────            │
│  ports/pdf_converter.py  │◄───│  pdf/gotenberg_pdf_converter.py [NEW]  │
│    [NEW]                 │    │    httpx.AsyncClient → Gotenberg       │
│  exceptions.py +         │    │  storage/minio_storage.py (existing)   │
│    PdfConversionError    │    │  persistence/models/document.py [MOD]  │
│  services/                │    │  alembic/010_pdf_export.py [NEW]       │
│    document_permissions.py│    │                                        │
│    [NEW]                 │    │                                        │
│  entities/document.py    │    │                                        │
│    [MODIFIED] dual fields│    │                                        │
└──────────────────────────┘    └────────────┬───────────────────────────┘
                                              │
                                ┌─────────────▼────────────┐
                                │  External                │
                                │  ────────────            │
                                │  gotenberg/gotenberg:8   │
                                │    POST /forms/          │
                                │      libreoffice/convert │
                                │  MinIO (existing)        │
                                └──────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Frontend                                                                │
│  ─────────                                                               │
│  shared/lib/auth.tsx (read user.role) [unchanged]                        │
│  features/documents/components/DynamicForm.tsx [MOD] split-button        │
│  features/documents/components/BulkGenerateFlow.tsx [MOD] + checkbox     │
│  components/ui/dropdown-menu.tsx [NEW] (shadcn primitive — not present)  │
└────────────────────────────────────────────────────────────────────────┘
```

## Architecture Decisions

### ADR-PDF-01: `PdfConverter` port shape — async, bytes-in/bytes-out

**Choice**: Async abstract method `convert(docx_bytes: bytes) -> bytes` raising `PdfConversionError`.

```python
# backend/src/app/domain/ports/pdf_converter.py
from abc import ABC, abstractmethod

class PdfConverter(ABC):
    @abstractmethod
    async def convert(self, docx_bytes: bytes) -> bytes: ...
```

`PdfConversionError(DomainError)` lives in `backend/src/app/domain/exceptions.py` (existing module — confirmed: contains `DomainError` and 8 sibling exceptions). Adapter MUST catch every `httpx` and HTTP-status failure and re-raise as `PdfConversionError`.

**Alternatives considered**: sync interface (rejected — `DocumentService.generate_single` is `async` end-to-end; sync wrapping would force `asyncio.to_thread` and serialise the event loop); file-path-based (rejected — current DOCX never touches disk; it lives in memory between `engine.render()` and `storage.upload_file()`).

**Rationale**: bytes-in/bytes-out matches the existing `TemplateEngine.render(file_bytes) -> bytes` contract. Async matches every other I/O port. The exception isolation is what makes `DocumentService` testable without mocking `httpx`. *Satisfies REQ-PDF-01, REQ-PDF-06, REQ-PDF-10.*

### ADR-PDF-02: Gotenberg HTTP contract

| Aspect | Decision |
|--------|----------|
| Endpoint | `POST {gotenberg_url}/forms/libreoffice/convert` |
| Body | `multipart/form-data`, single field `files` with `filename="document.docx"` and `content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"` |
| Timeouts | `httpx.Timeout(connect=5.0, read=settings.gotenberg_timeout, write=10.0, pool=5.0)` — `gotenberg_timeout` defaults to 60s |
| Retry policy | NONE in v1 (atomic semantics — see ADR-PDF-03) |
| Healthcheck | docker-compose: `test: ["CMD", "curl", "-f", "http://localhost:3000/health"]`; api `depends_on: gotenberg: condition: service_healthy` |
| Networking | container DNS `gotenberg` on `sigdoc` network → `GOTENBERG_URL=http://gotenberg:3000` |
| Host port | NOT exposed — internal-only; Gotenberg has no admin UI worth exposing |

A `httpx.AsyncClient` is created per call (lifecycle = single conversion). No client pool in v1 — Gotenberg's LibreOffice bottleneck is the conversion itself, not connection setup. *Satisfies REQ-PDF-02, REQ-PDF-03, REQ-PDF-05, REQ-PDF-08.*

### ADR-PDF-03: Atomic generation flow

`DocumentService.generate_single` pseudo-code:

```
1. Quota check                                    (existing)
2. Fetch template version + access check          (existing)
3. Download template bytes from MinIO             (existing)
4. rendered_docx = engine.render(template, vars)  (existing)
5. doc_id = uuid4()
   docx_path = f"{tenant_id}/{doc_id}/{name}.docx"
   pdf_path  = f"{tenant_id}/{doc_id}/{name}.pdf"
6. await storage.upload_file(DOCS, docx_path, rendered_docx, DOCX_MIME)  ── checkpoint A
7. try:
       pdf_bytes = await pdf_converter.convert(rendered_docx)             ── checkpoint B
   except PdfConversionError:
       await storage.delete_file(DOCS, docx_path)   # rollback A
       raise                                         # presentation maps → 503
8. await storage.upload_file(DOCS, pdf_path, pdf_bytes, PDF_MIME)         ── checkpoint C
9. document = Document(... docx_file_name, pdf_file_name, docx_minio_path, pdf_minio_path ...)
   await doc_repo.create(document)                                        ── checkpoint D
10. usage + audit (formats_generated=["docx","pdf"]) — fire-and-forget after D
11. return {document, download_url(format=pdf)}
```

DB persistence (step 9) is a single `INSERT`; no need for an explicit transaction wrapper — SQLAlchemy session commits on the request boundary. If step 8 fails (PDF upload), we delete the orphan DOCX from MinIO before raising; the row was never created. If step 9 fails (extremely rare — DB constraint violation), both MinIO objects are cleaned up.

**Bulk variant**: same flow per row, sequential. If ANY row fails conversion at step 7, ALL prior rows for this batch have their DOCX *and* PDF cleaned up from MinIO; no `Document` rows persist; the API responds 503. **Rationale**: atomic semantics MUST be uniform — partial bulk success would create the same "is this legacy or did Gotenberg fail?" ambiguity rejected in proposal decision 6.

*Satisfies REQ-DDF-03, REQ-DDF-04, REQ-DDF-05, REQ-DDF-14, REQ-DDF-16.*

### ADR-PDF-04: Lazy backfill semantics

A NEW method `DocumentService.ensure_pdf(document_id) -> Document` performs backfill. It lives in the service, not the endpoint, so the hexagonal boundary stays clean.

```
async def ensure_pdf(self, document_id: UUID) -> Document:
    doc = await self._doc_repo.get_by_id(document_id)
    if doc is None: raise DocumentNotFoundError
    if doc.pdf_file_name is not None: return doc    # idempotent fast path
    docx_bytes = await self._storage.download_file(DOCS, doc.docx_minio_path)
    pdf_bytes  = await self._pdf_converter.convert(docx_bytes)   # raises → caller maps 503
    pdf_name   = doc.docx_file_name.removesuffix(".docx") + ".pdf"
    pdf_path   = f"{doc.tenant_id}/{doc.id}/{pdf_name}"
    await self._storage.upload_file(DOCS, pdf_path, pdf_bytes, PDF_MIME)
    return await self._doc_repo.update_pdf_fields(doc.id, pdf_name, pdf_path)
```

**Concurrency**: rely on idempotency, not row locks. If two requests race, both upload (same content, last-write-wins on MinIO key — but each has a distinct path because `pdf_name` is deterministic from `docx_file_name`, so the path is identical and MinIO overwrites cleanly). The DB UPDATE is a single statement; whichever commits second is a no-op semantically. **Rejected**: `SELECT ... FOR UPDATE` adds operational complexity for an event that, per the proposal's risks table, is rare-and-low-impact (legacy backfill on first read).

**Backfill failure**: PDF upload + DB update never run; row stays `pdf_file_name IS NULL`; endpoint returns 503; row is retryable on the next request. The original DOCX is NOT touched (it predates this request).

**Admin-on-legacy-PDF resolution (SPEC GAP #3)**: The role check is for the FORMAT (`can_download_format`). The backfill trigger is `pdf_file_name IS NULL AND format == "pdf"` — role-agnostic. So an admin requesting `format=pdf` on a legacy doc triggers identical lazy backfill. SCEN-DDF-08 (admin DOCX on legacy → no backfill) and the new behavior (admin PDF on legacy → backfill) are consistent: backfill follows the format requested, not the role. **No spec change needed** — REQ-DDF-09 already says "regardless of the requester's role".

*Satisfies REQ-DDF-09, REQ-DDF-10.*

### ADR-PDF-05: RBAC permission helper

```python
# backend/src/app/domain/services/document_permissions.py
DOWNLOAD_FORMAT_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"docx", "pdf"}),
    "user":  frozenset({"pdf"}),
}

def can_download_format(role: str, format: str) -> bool:
    return format in DOWNLOAD_FORMAT_PERMISSIONS.get(role, frozenset({"pdf"}))
```

**Choice**: dict-based table over `Enum + matrix`. Adding a new role is a one-line dict update; adding a new format is a one-line frozenset extension. An Enum forces a recompile-style change set with multiple touch points.

**Module location**: `backend/src/app/domain/services/document_permissions.py`. The directory `domain/services/` does NOT exist yet — `__init__.py` and the file are both new. **Default for unknown roles**: PDF-only (safe — defaults to most-restrictive non-empty set; never zero-permission to keep happy paths working when SaaS adds future roles like `auditor` without a code update).

**Test contract** lives in `backend/tests/unit/domain/test_document_permissions.py` and asserts the SCEN-DDF-16 truth table: `(admin,docx)→T`, `(admin,pdf)→T`, `(user,docx)→F`, `(user,pdf)→T`, `(unknown,docx)→F`, `(unknown,pdf)→T`. *Satisfies REQ-DDF-08.*

### ADR-PDF-06: Migration `010_pdf_export.py`

Verified against `backend/src/app/infrastructure/persistence/models/document.py`: current columns are `minio_path: VARCHAR(500) NOT NULL` and `file_name: VARCHAR(255) NOT NULL`.

```python
def upgrade() -> None:
    op.alter_column("documents", "file_name",  new_column_name="docx_file_name")
    op.alter_column("documents", "minio_path", new_column_name="docx_minio_path")
    op.add_column("documents", sa.Column("pdf_file_name",  sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("pdf_minio_path", sa.String(500), nullable=True))

def downgrade() -> None:
    op.drop_column("documents", "pdf_minio_path")
    op.drop_column("documents", "pdf_file_name")
    op.alter_column("documents", "docx_minio_path", new_column_name="minio_path")
    op.alter_column("documents", "docx_file_name",  new_column_name="file_name")
```

**No data backfill at migration time** — REQ-DDF-02 explicitly requires NULL pdf fields as the legacy sentinel. PDF orphans on downgrade are tolerated (a one-shot cleanup script can drop them — out of scope for this change).

`revision: str = "010"`, `down_revision = "009"` (latest migration is 009, verified). *Satisfies REQ-DDF-01, REQ-DDF-02.*

### ADR-PDF-07: `via=share` detection (SPEC GAP #1)

**Decision**: explicit query param on the download endpoint, validated by the service against template_shares membership.

```python
# GET /documents/{id}/download?format=pdf|docx&via=direct|share   (via defaults to "direct")
@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    format: Literal["pdf","docx"] = Query(...),
    via: Literal["direct","share"] = Query("direct"),
    current_user: CurrentUser = Depends(get_current_user),
    ...
):
    ...
```

The frontend KNOWS which UI it's rendering — the share-recipient inbox path passes `via=share`, the owner's documents page passes `via=direct` (default). Backend treats `via` as a hint that gets sanity-checked: if `via=share` but `current_user` is the document creator AND the underlying template is owned (not shared), the backend overrides it to `via=direct` (audit integrity).

**Alternatives considered**:
- (a) Separate endpoint `/shared/documents/{id}/download` — rejected: doubles the endpoint count for one audit field; the RBAC + backfill logic is identical.
- (b) Implicit detection from `template_shares` membership — rejected: requires an extra DB roundtrip on EVERY download just to set one audit field; also ambiguous when an admin downloads their own doc generated from a self-shared template.
- (c) Header-based — rejected: query params are visibly inspectable by ops/audit; headers are hidden from server logs by default.
- (d) Service-layer-only flag with no API surface — rejected: client must declare intent for the audit trail to be meaningful.

**Rationale**: The frontend renders different UIs for "my documents" vs "shared with me" — it KNOWS the context. Forcing the backend to re-derive context defeats hexagonal layering. The sanity check ensures audit integrity even if a malicious client lies about `via`.

*Satisfies REQ-DDF-15.*

### ADR-PDF-08: Bulk download with legacy rows (SPEC GAP #2)

**Decision**: serial backfill before zipping; entire ZIP fails 503 if ANY backfill fails.

```
for each doc in batch:
    if doc.pdf_file_name is None and format in (pdf, both):
        await ensure_pdf(doc.id)   # may raise PdfConversionError
zip = build_zip(...)
```

**Latency profile** (worst case): a tier with `bulk_generation_limit=50`, all rows legacy, Gotenberg ~3s per conversion → 150s. Acceptable: bulk download is already a "click and wait" UX; the user is downloading dozens of files. The proposal's existing `bulk_generation_limit` already bounds this — no new knob needed.

**Alternatives considered**:
| Option | Tradeoff | Verdict |
|--------|----------|---------|
| (a) Serial backfill | Slow but predictable, atomic | **Picked** |
| (b) Skip legacy with header warning | Silent data loss; user expects all PDFs | Rejected |
| (c) Parallel pool (e.g. 4 workers) | Faster; but Gotenberg already bottlenecks on LibreOffice | Rejected for v1 |
| (d) Fail batch on first NULL | More aggressive than spec requires | Rejected |

**Rationale**: serial matches the proposal's "atomic" stance — partial PDFs in the ZIP would be the bulk-equivalent of partial bulk success at generation time, which we already rejected. Parallel could be a v2 if observed latency is a problem.

### ADR-PDF-09: Frontend download UX

**shadcn dropdown is NOT installed** — verified: `frontend/src/components/ui/` contains badge, button, card, dialog, input, label, progress, select, skeleton, sonner, table, tabs, textarea. NO `dropdown-menu.tsx`. The tasks phase MUST add it via `npx shadcn-ui@latest add dropdown-menu` (which lays down `components/ui/dropdown-menu.tsx` using Radix UI primitives).

**Component**: a single new component `frontend/src/features/documents/components/DownloadButton.tsx` encapsulates role logic:

```tsx
function DownloadButton({ documentId, via = "direct" }: Props) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  if (!isAdmin) return <Button onClick={() => download(documentId, "pdf", via)}>Descargar PDF</Button>;
  return <DropdownMenu>...PDF + DOCX items...</DropdownMenu>;
}
```

Role accessor: `useAuth().user.role === "admin"` — verified in `frontend/src/shared/lib/auth.tsx` (`User.role: string`). Bulk variant `BulkDownloadControls.tsx` adds the admin-only checkbox alongside the same button. *Satisfies REQ-DDF-17, REQ-DDF-18.*

### ADR-PDF-10: Test strategy

| Layer | File | What |
|-------|------|------|
| Unit (domain) | `tests/unit/domain/test_document_permissions.py` | Truth table from SCEN-DDF-16 |
| Unit (infra) | `tests/unit/infrastructure/test_gotenberg_pdf_converter.py` | `respx`-mocked Gotenberg: 200, 4xx, 5xx, timeout, connect-error all map to `PdfConversionError` |
| Unit (app) | `tests/unit/application/test_document_service_pdf.py` | Atomic rollback on convert failure (DOCX deleted, no row); successful dual-format persistence; lazy backfill happy + failure |
| Integration | `tests/integration/api/test_pdf_export.py` | E2E with `FakePdfConverter`: SCEN-DDF-01 through 16 |
| Fakes | `tests/fakes/fake_pdf_converter.py` | `convert_result` + `set_failure(exc)` per REQ-PDF-07 |

Test runner: `pytest` with `pytest-asyncio` (verified by the project's existing `tests/` structure mirroring this pattern). `respx>=0.20` is a new test dep (`[project.optional-dependencies] dev`).

## Data Flow

Generation (single, happy path):

```
client → POST /generate
              │
              ▼
         DocumentService.generate_single
              │
   ┌──────────┼─────────────┐
   ▼          ▼             ▼
 MinIO     Gotenberg     postgres
 (DOCX)    (DOCX→PDF)    (Document)
   │          │             │
   └──────────┼─────────────┘
              ▼
         Audit (formats=["docx","pdf"])
              │
              ▼
         {document, download_url}
```

Download (legacy lazy backfill):

```
client → GET /{id}/download?format=pdf
              │
              ▼
         can_download_format(role, "pdf") ───[False]──→ 403
              │ True
              ▼
         service.ensure_pdf(id)
              │
              ▼  (pdf_file_name IS NULL?)
   ┌──────────┴─────────────┐
   │ NO                     │ YES
   ▼                        ▼
fast path              MinIO get DOCX → Gotenberg → MinIO put PDF
                            │                       │
                            ▼                       ▼
                       update Document         (raise → 503, no DB write)
              │
              ▼
         MinIO get PDF → Response (PDF + audit via=direct|share)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/app/domain/ports/pdf_converter.py` | Create | `PdfConverter` ABC |
| `backend/src/app/domain/exceptions.py` | Modify | Add `PdfConversionError(DomainError)` |
| `backend/src/app/domain/services/__init__.py` | Create | Empty package init |
| `backend/src/app/domain/services/document_permissions.py` | Create | `DOWNLOAD_FORMAT_PERMISSIONS` + `can_download_format` |
| `backend/src/app/domain/entities/document.py` | Modify | Add `docx_file_name`, `pdf_file_name`, `docx_minio_path`, `pdf_minio_path`; remove `file_name`, `minio_path` |
| `backend/src/app/domain/entities/audit_log.py` | Modify | Add `AuditAction.DOCUMENT_DOWNLOAD = "document.download"` |
| `backend/src/app/infrastructure/pdf/__init__.py` | Create | `@lru_cache` `get_pdf_converter()` |
| `backend/src/app/infrastructure/pdf/gotenberg_pdf_converter.py` | Create | httpx async adapter |
| `backend/src/app/infrastructure/persistence/models/document.py` | Modify | New columns + nullable PDF fields |
| `backend/src/app/infrastructure/persistence/repositories/document_repository.py` | Modify | `update_pdf_fields(id, name, path)` method |
| `backend/alembic/versions/010_pdf_export.py` | Create | Rename + add columns |
| `backend/src/app/application/services/document_service.py` | Modify | Atomic dual-format flow; `ensure_pdf` |
| `backend/src/app/application/services/__init__.py` | Modify | Wire `PdfConverter` into `get_document_service()` |
| `backend/src/app/presentation/api/v1/documents.py` | Modify | `format` + `via` + `include_both` params; RBAC + 403/422/503 mapping |
| `backend/src/app/presentation/schemas/document.py` | Modify | Drop `output_format` |
| `backend/src/app/config.py` | Modify | `gotenberg_url`, `gotenberg_timeout` |
| `backend/pyproject.toml` | Modify | Promote `httpx`; add `respx` to dev |
| `docker/docker-compose.yml` | Modify | Add `gotenberg` service + healthcheck + `api.depends_on` |
| `backend/tests/fakes/fake_pdf_converter.py` | Create | `FakePdfConverter` |
| `backend/tests/unit/domain/test_document_permissions.py` | Create | Truth table |
| `backend/tests/unit/infrastructure/test_gotenberg_pdf_converter.py` | Create | respx adapter tests |
| `backend/tests/unit/application/test_document_service_pdf.py` | Create | Atomic + backfill |
| `backend/tests/integration/api/test_pdf_export.py` | Create | E2E SCEN-DDF-01..16 |
| `frontend/src/components/ui/dropdown-menu.tsx` | Create | shadcn add dropdown-menu |
| `frontend/src/features/documents/components/DownloadButton.tsx` | Create | Role-aware download |
| `frontend/src/features/documents/components/BulkDownloadControls.tsx` | Create | Bulk + admin checkbox |
| `frontend/src/features/documents/api/queries.ts` | Modify | URL builder takes `format` + optional `via` |
| `frontend/src/features/documents/api/mutations.ts` | Modify | Drop `output_format` |
| `frontend/src/features/documents/components/DynamicForm.tsx` | Modify | Replace download trigger with `DownloadButton` |
| `frontend/src/features/documents/components/BulkGenerateFlow.tsx` | Modify | Replace bulk download trigger with `BulkDownloadControls` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|--------------|----------|
| Unit (domain) | `can_download_format` truth table | Pure function — parametrized pytest |
| Unit (infra) | Gotenberg adapter HTTP semantics | `respx` mock for 2xx/4xx/5xx/timeout/connect-error |
| Unit (app) | Atomic rollback, lazy backfill | `FakeStorageService` + `FakePdfConverter` |
| Integration | All 16 spec scenarios | FastAPI `TestClient` + sqlite/in-memory or testcontainer postgres |

## Migration / Rollout

1. Deploy migration `010_pdf_export.py` → existing rows have NULL pdf fields
2. Deploy backend with `gotenberg` service in compose → all NEW generations dual-format
3. Deploy frontend with role-aware UI
4. Legacy rows lazy-backfill on first PDF download

No feature flag — the change is a hard cutover. Rollback per the proposal's plan.

## Open Questions

- (none blocking) `respx` version pin: latest stable is `0.21.x`; I recommend `>=0.20.0,<1.0`. Resolve in tasks phase.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Orphan PDF in MinIO if download endpoint races backfill (last-write-wins on identical path is fine, but a concurrent ensure_pdf where one fails after upload but before DB commit leaks the PDF object) | Low | Document as known. Out-of-scope cleanup script can reconcile against DB monthly. |
| Gotenberg version drift across environments (no pin in compose tag) | Medium | Pin `gotenberg/gotenberg:8` (exact major) — already specified. Tasks phase to consider `:8.7` or similar minor pin. |
| Bulk download timeout for many legacy rows (150s worst case) | Low | Documented latency profile in ADR-PDF-08; reverse proxy timeout (nginx) MUST allow 5min+ for `/bulk/*/download`. |
| `via=share` audit field can be lied about by client | Low | ADR-PDF-07 sanity check overrides `via=share` to `via=direct` when current_user is the doc creator AND template is owned. |
| Frontend split-button is a regression for keyboard users | Low | shadcn dropdown-menu uses Radix — keyboard accessible by default. Verify in QA. |
| Large DOCX files (>10 MB) push Gotenberg memory | Low | Existing `bulk_generation_limit` indirectly bounds; document as ops note. |

---

**Ready for**: `sdd-tasks` phase.
