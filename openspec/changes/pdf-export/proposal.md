# Proposal: PDF Export via Gotenberg (with role-gated download)

**Change ID:** `pdf-export`

## Why

This is a **regulated medical SaaS**. Generated documents (clinical reports, patient communications, etc.) become part of a record that must remain trustworthy. **DOCX files are editable; PDF files are not.** Letting non-admin operators pull the editable Word file is a document-integrity risk: a downstream party could not tell whether the file they received matched what was originally generated.

Therefore PDF is no longer an "additional output format" — it is the **canonical, tamper-resistant artifact** that the platform must produce on every generation, and it is the only format that ordinary users may download. Admins keep DOCX access for legitimate template-correction workflows. This change introduces:

1. Mandatory dual-format generation (DOCX + PDF) on every `generate` / `generate-bulk` call, via a new `PdfConverter` port + Gotenberg adapter.
2. Role-based download enforcement (`admin` → DOCX or PDF, `user` → PDF only) via a single permission helper that future roles can extend.
3. Lazy, idempotent backfill for documents created before this change so no historical record becomes unreachable for non-admin users.

## What Changes

- New domain port `PdfConverter` + exception `PdfConversionError`.
- New infrastructure adapter `GotenbergPdfConverter` (httpx) + `@lru_cache` factory.
- New domain module `document_permissions.py` exposing `can_download_format(role, format) -> bool` with a single source-of-truth dict (`DOWNLOAD_FORMAT_PERMISSIONS`).
- `DocumentService.generate_single` / `generate_bulk` ALWAYS produce both DOCX and PDF. The `output_format` request field is **removed**.
- `Document` entity gains `docx_file_name` and `pdf_file_name`; existing `file_name` is migrated → renamed to `docx_file_name`. `pdf_file_name` is nullable in the schema (legacy rows) but treated as required for new rows.
- `Document` also gains a `pdf_minio_path` field alongside the existing `minio_path` (which is renamed `docx_minio_path`); both are populated at generation time.
- API: `GET /documents/{id}/download` requires a `format=pdf|docx` query parameter; it RBAC-checks via `can_download_format`. `GET /documents/bulk/{batch_id}/download` requires `format` and accepts `include_both=bool` (admin-only, ignored for non-admin).
- Generation endpoints (`POST /documents/generate`, `POST /documents/generate-bulk`) no longer accept `output_format`.
- Frontend: split-button download with role-aware menu (admin sees DOCX + PDF; non-admin sees PDF only); bulk view gains an admin-only "Include Word documents" checkbox.
- Alembic migration `010_pdf_export.py`: rename column, add new column(s), nullable backfill strategy.
- Audit: every download writes `details = {"format": "...", "document_id": "..."}`; every generation writes `details.formats_generated = ["docx", "pdf"]`.
- Docker Compose: `gotenberg` sidecar + healthcheck dependency.
- `httpx` promoted from `[project.optional-dependencies] dev` to `[project.dependencies]` (pin `>=0.27.0,<1.0`).
- Tests: `FakePdfConverter`, unit tests for `document_permissions.py`, integration tests for end-to-end PDF + RBAC + legacy backfill.

## Out of Scope

- **Codebase-wide RBAC refactor.** The codebase has ~15 sites with hard-coded `role == "admin"` checks (verified: `users.py:26,148,150,204`, `templates.py:311`, `usage.py:27`, `audit.py:55`, `documents.py:239`, `template_repository.py:167,311`, `user_repository.py:84`, `template_service.py:145`, etc.). This change does NOT migrate them. The new `document_permissions.py` is **scoped to the download-format concern only**. Future work can generalize the helper, but that work is not part of this change.
- Custom PDF styling, watermarks, digital signatures.
- Async/background generation, queueing, retries.
- Attaching PDFs to share-by-email payloads (still link-only).
- Separate PDF rate-limit tier or separate PDF quota counter.
- A standalone PDF re-conversion endpoint (the legacy backfill path covers the only case that needs it).
- Hard cleanup job to backfill all legacy PDFs upfront (lazy backfill is sufficient).

## Decisions

1. **PDF lifecycle — generated alongside DOCX.** Every successful `generate*` call produces and persists BOTH DOCX and PDF to MinIO before returning. PDF is no longer optional, no longer on-demand. Rationale: document integrity is a non-negotiable business rule for this medical SaaS; the editable artifact and the canonical artifact must coexist from t=0 so non-admin users always have something to pull.

2. **Document data model — option A1 (single row, dual file fields).** One `Document` row references both files. Add `docx_file_name`, `pdf_file_name`, `docx_minio_path`, `pdf_minio_path`; rename existing `file_name` → `docx_file_name` and `minio_path` → `docx_minio_path`. PDF columns are nullable at the SQL level so historical rows remain valid; service layer treats them as required for new generations. Rejected: separate child table (over-engineered; 1:1 relation), keeping `file_name` polymorphic (would force JOIN-time format inference). Migration: `010_pdf_export.py`.

3. **Audit logging — extend `details`.** Reuse existing `AuditAction.DOCUMENT_GENERATE` and `DOCUMENT_GENERATE_BULK`; generation events get `details.formats_generated = ["docx", "pdf"]`. Add a new `AuditAction.DOCUMENT_DOWNLOAD = "document.download"` for download events with `details = {"format": "pdf"|"docx", "document_id": "..."}`. Rationale: download was previously implicit; given the new RBAC dimension, downloads need their own auditable trace. Rejected: piggyback download on generate (loses temporal granularity); a per-format AuditAction (breaks audit query simplicity).

4. **Endpoint shape.**
   - `POST /documents/generate` — body has NO `output_format`. Always generates both.
   - `POST /documents/generate-bulk` — same.
   - `GET /documents/{id}/download?format=pdf|docx` — `format` is required (422 if missing); RBAC-checked via `can_download_format`.
   - `GET /documents/bulk/{batch_id}/download?format=pdf|docx&include_both=false` — admin-only `include_both=true` returns ZIP with both formats per row (e.g. `row1.docx`, `row1.pdf`). For non-admin: `include_both=true` is rejected with 403 (loud rather than silently ignored — the user is asking for something they cannot have, and a 403 makes the boundary visible to client-side code). `format` is still required; for non-admin only `format=pdf` is accepted.

5. **Bulk PDF.** Bulk generation always produces both formats per row. Bulk download endpoint RBAC-checks `format`; non-admin ZIPs contain only PDFs.

6. **Failure mode — atomic (B1).** If Gotenberg conversion fails for ANY row in a single `generate*` request, the entire operation fails with HTTP 503 `PdfConversionError`. No DOCX-only fallback. No partial success. Rationale: a partial success would create rows where `pdf_file_name IS NULL`, which would be indistinguishable from a legitimate legacy row and would silently route through the lazy-backfill path on the next request — masking a systemic outage. Failing loudly forces the operator to retry once Gotenberg is healthy.
   - **Cleanup on failure**: when DOCX upload succeeded but PDF conversion failed, the service deletes the orphan DOCX from MinIO before raising. No `Document` row is persisted. (Cleanest option: the row never existed, so there is nothing for an external observer to reconcile.)

7. **httpx promotion.** Move `httpx` from `[project.optional-dependencies] dev` to `[project.dependencies]`; keep pin `>=0.27.0,<1.0`. Already pinned in dev; trivial.

8. **Where conversion happens.** Application service layer. `DocumentService.generate_*` orchestrates: render DOCX bytes → upload DOCX → `pdf_converter.convert(docx_bytes)` → upload PDF → persist `Document` row with both file names + paths. Single transaction-like flow with explicit cleanup on failure (decision 6). Rejected: presentation-layer adapter (leaks infra), background worker (no queue infrastructure exists; non-trivial change).

9. **Sharing inherits the recipient's role (D-yes).** When a user accesses a document they reached via a `template_shares` link or a share-by-email flow, RBAC is enforced against the **recipient's** role on each download, not the sharer's. If an `admin` shares a template with a `user`, anything that `user` then generates and downloads obeys the `user` PDF-only rule. The check happens at the download endpoint via `can_download_format(current_user.role, format)`, so this is automatic — no special path is needed in the share service. **Spec must explicitly cover this scenario.**

10. **Quota — F-1.** A single `generate*` call producing DOCX + PDF counts as **1** against `monthly_document_limit`. The pair is one logical document; dual-format is an implementation detail of the integrity guarantee, not a separately-billable resource.

11. **Frontend UX — split-button dropdown.**
    - Admin: split button with caret → menu items "Descargar como PDF" and "Descargar como Word".
    - Non-admin: single plain button "Descargar PDF" (no caret, no menu, Word option not rendered at all — not just disabled).
    - Bulk view: same logic, plus admin sees a checkbox "Incluir documentos Word" that toggles `include_both=true`.
    - Role is derived from the existing auth context (`useCurrentUser` / equivalent) — no extra API call.

12. **Legacy docs lazy backfill — G3.** Documents created before this change have `pdf_file_name IS NULL`. On a non-admin request to `GET /{id}/download?format=pdf`:
    - Service detects null PDF.
    - Pulls DOCX from MinIO, calls `pdf_converter.convert`, uploads PDF, updates the row with `pdf_file_name` + `pdf_minio_path`.
    - Returns the PDF bytes.
    - Idempotent: subsequent requests find the persisted PDF and skip conversion.
    - Admin requesting `format=docx` on a legacy doc works as before (no conversion needed).
    - Admin requesting `format=pdf` on a legacy doc also triggers backfill (consistency).
    - If the backfill conversion fails, return 503 `PdfConversionError` and do NOT persist anything (same atomic semantics as decision 6).

13. **Permission helper for forward extensibility (NEW).** A single domain module owns the format-RBAC concern:

    ```python
    # backend/src/app/domain/services/document_permissions.py
    DOWNLOAD_FORMAT_PERMISSIONS: dict[str, frozenset[str]] = {
        "admin": frozenset({"docx", "pdf"}),
        "user": frozenset({"pdf"}),
    }

    def can_download_format(role: str, format: str) -> bool:
        return format in DOWNLOAD_FORMAT_PERMISSIONS.get(role, frozenset({"pdf"}))
    # Default for unknown roles: PDF-only — safe by design.
    ```

    Both download endpoints (`/documents/{id}/download` and `/documents/bulk/{batch_id}/download`) call this helper. The endpoint translates a `False` return into HTTP 403 with a clear message ("This format is not available for your role"). **Constraint for downstream phases**: spec and design MUST require that no other code path makes its own role-vs-format decision. Adding a new role (e.g. `auditor`, `external_reviewer`) is a one-line dict update; adding a new format is also localized here. The hard-coded `role == "admin"` checks elsewhere in the codebase are out of scope for this change (see "Out of Scope") but the helper is the seed for a future RBAC unification.

## Module Map

```
backend/src/app/domain/ports/pdf_converter.py                                    [NEW]
backend/src/app/domain/exceptions.py                                             [MODIFY] add PdfConversionError, FormatNotPermittedError
backend/src/app/domain/services/__init__.py                                      [NEW] (folder did not exist before)
backend/src/app/domain/services/document_permissions.py                          [NEW] DOWNLOAD_FORMAT_PERMISSIONS, can_download_format
backend/src/app/domain/entities/document.py                                      [MODIFY] add docx_file_name, pdf_file_name, docx_minio_path, pdf_minio_path; deprecate file_name/minio_path aliases
backend/src/app/infrastructure/pdf/__init__.py                                   [NEW] @lru_cache get_pdf_converter()
backend/src/app/infrastructure/pdf/gotenberg_pdf_converter.py                    [NEW]
backend/src/app/infrastructure/persistence/models/document.py                    [MODIFY] add new columns; update __table_args__ if needed
backend/alembic/versions/010_pdf_export.py                                       [NEW] rename file_name→docx_file_name, minio_path→docx_minio_path; add pdf_file_name (nullable), pdf_minio_path (nullable)
backend/src/app/application/services/document_service.py                         [MODIFY] generate both formats atomically; cleanup on failure; lazy backfill on read
backend/src/app/application/services/__init__.py                                 [MODIFY] inject PdfConverter into DocumentService
backend/src/app/application/services/audit_service.py                            [MODIFY] (if needed) accept new DOCUMENT_DOWNLOAD action
backend/src/app/domain/entities/audit_log.py                                     [MODIFY] add AuditAction.DOCUMENT_DOWNLOAD
backend/src/app/presentation/api/v1/documents.py                                 [MODIFY] download endpoints take format query param; call can_download_format; raise 403 on denial
backend/src/app/presentation/schemas/document.py (or schemas.py)                 [MODIFY] remove output_format from GenerateRequest; add format query schema
backend/src/app/config.py                                                        [MODIFY] gotenberg_url, gotenberg_timeout
backend/pyproject.toml                                                           [MODIFY] promote httpx
docker/docker-compose.yml                                                        [MODIFY] gotenberg service + healthcheck + api depends_on
backend/tests/fakes/fake_pdf_converter.py                                        [NEW]
backend/tests/unit/domain/test_document_permissions.py                           [NEW]
backend/tests/unit/application/test_document_service_pdf.py                      [NEW]
backend/tests/integration/api/test_pdf_export.py                                 [NEW] happy path, 403, Gotenberg-down, legacy backfill, bulk, sharing
frontend/src/features/documents/api/mutations.ts                                 [MODIFY] remove output_format from request payloads
frontend/src/features/documents/api/queries.ts                                   [MODIFY] download URL builder takes format
frontend/src/features/documents/components/DynamicForm.tsx                       [MODIFY] split-button download (role-aware)
frontend/src/features/documents/components/BulkGenerateFlow.tsx                  [MODIFY] split-button + admin "Incluir Word" checkbox
frontend/src/features/documents/components/DocumentList.tsx                      [MODIFY] (if it has download actions) split-button per row
```

Notes on paths verified in the codebase:
- Config lives at `backend/src/app/config.py`, NOT `backend/src/app/core/config.py`.
- `backend/src/app/domain/services/` does not exist yet; it will be created for `document_permissions.py`.
- There is no `backend/src/app/presentation/api/v1/share.py`; share endpoints live inside `templates.py` (`/{template_id}/shares`). They do NOT need RBAC changes for this proposal because the format check happens at document download time, not at share time. Decision 9 holds automatically.
- Document model has both `minio_path` and `file_name` today — both are renamed/extended, not just `file_name`.

## Success Criteria

- [ ] Generating a document (single or bulk) produces and persists BOTH `docx` and `pdf` to MinIO before the API responds.
- [ ] `Document` row stores both `docx_file_name`/`docx_minio_path` and `pdf_file_name`/`pdf_minio_path` (the latter nullable for legacy rows only).
- [ ] Admin (`role == "admin"`) can download both formats from the single-doc endpoint.
- [ ] Non-admin (any other role) can ONLY download PDF; requesting `format=docx` returns HTTP 403 with a clear, non-leaky message.
- [ ] Sharing inherits the recipient's role: a `user` who reaches a document via a `template_shares` link still cannot download DOCX.
- [ ] Gotenberg failure during a fresh generation → entire request fails atomically with HTTP 503; no orphan DOCX in MinIO; no `Document` row created.
- [ ] Legacy docs (created before this change, `pdf_file_name IS NULL`) get a PDF generated and persisted on first download request requiring it; the same row is updated; subsequent requests skip conversion.
- [ ] Backfill failure during a legacy doc download → 503; the legacy row is NOT corrupted (no partial update).
- [ ] Quota: a single `generate*` call counts as 1 document against `monthly_document_limit`, regardless of dual-format output.
- [ ] Bulk download for non-admin returns ZIP of PDFs only.
- [ ] Bulk download for admin with `include_both=true` returns a ZIP containing `row{N}.docx` and `row{N}.pdf` for each generated row.
- [ ] Bulk download for non-admin with `include_both=true` → HTTP 403 (loud rejection).
- [ ] Audit log records `details.format` on every download, `details.formats_generated` on every generation.
- [ ] `can_download_format()` is the ONLY place in the codebase that decides which role gets which format. (Verified by spec/design + reviewer checklist.)
- [ ] Existing DOCX flow remains regression-safe for admin users.
- [ ] `httpx` is a production dependency in `pyproject.toml`.
- [ ] `gotenberg` healthcheck passes in `docker compose up`; API starts only after.
- [ ] Tests cover: happy path (single + bulk), non-admin 403 on DOCX request, Gotenberg-down 503 on fresh generation, legacy backfill happy path + failure path, bulk admin `include_both`, sharing recipient-role enforcement, `can_download_format` unit table.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Storage doubles per document (PDF + DOCX always co-stored) | High (by design) | Operational heads-up: MinIO sizing must accommodate ~2× bytes per generation. Document in deployment notes. |
| Gotenberg becomes a hard dependency for ALL generations (not optional anymore) | High | Healthcheck dependency in compose; clear 503 mapping; runbook entry for "Gotenberg down" SOP; consider Gotenberg replicas for prod. |
| Migration `010` must handle existing rows without dropping data | Med | Migration: rename columns (preserves data); add nullable PDF columns. No NOT NULL backfill at migration time — lazy on read. |
| Lazy backfill adds latency on first request for legacy docs (~1–5s) | Low | Acceptable trade vs. an upfront migration that would touch every historical row and run Gotenberg N times. Document the behavior. Optional follow-up: a one-shot management command to pre-warm. |
| Bulk PDF memory spikes (LibreOffice 200–400 MB/conv) | Med | Sequential (not concurrent) Gotenberg calls in bulk; existing `bulk_generation_limit` caps N. |
| Conversion fidelity loss on complex DOCX | Low | Documented limitation; LibreOffice is industry-standard for this approach. |
| `can_download_format` drift: someone adds a new download path and forgets to call it | Low | Spec + reviewer checklist explicitly require it; integration tests assert 403 for `user`+`docx`. |
| httpx promotion forgotten | Low | Tasks phase makes this an explicit checklist item; CI build will fail without it. |
| Frontend leaks DOCX option to non-admin via stale role state | Low | UI derives role from server-supplied auth context only; backend is the source of truth and rejects regardless. Defense in depth. |

## Rollback Plan

This change is harder to roll back than the v1 plan because the schema and behavior shift simultaneously:

1. **If discovered before any non-admin-attempted download**: revert frontend (split-button → original button), revert API to optional `output_format` (default `docx`), keep `gotenberg` running OR remove it. Existing DB rows still have `docx_file_name`/`docx_minio_path` (just renamed) — backwards-compatible read path can alias them back to `file_name`/`minio_path`.
2. **If discovered after non-admin downloads**: PDF rows in MinIO are valid PDFs and remain accessible; rolling back simply means the UI no longer offers PDF. No data loss.
3. **DB rollback**: Alembic `downgrade()` renames columns back; PDF columns are dropped. PDF MinIO objects become orphaned — can be cleaned with a one-shot script.
4. The `PdfConverter` port + adapter can stay in tree as dead code or be reverted in the same PR.

## Capabilities

### New Capabilities

- **`pdf-conversion`** — domain port `PdfConverter`, exception `PdfConversionError`, Gotenberg adapter, configuration, failure semantics.
- **`document-download-format`** — end-to-end ability to choose `docx` or `pdf` on download, including request schema, audit `details.format`, MIME detection, frontend split-button, **AND role-based access enforcement via `can_download_format`** (this capability now also owns the RBAC concern for the format dimension).

### Modified Capabilities

- None pre-existing in `openspec/specs/`. This change introduces the first two.

## Dependencies

- New runtime dep: `httpx>=0.27.0,<1.0` (promotion).
- New container: `gotenberg/gotenberg:8`.

## Notes for Downstream Phases

- **Strict TDD Mode is active.** Write tests first — particularly the unit table for `can_download_format` and the integration tests for 403 paths. The tests are themselves part of the contract because the RBAC rule is the load-bearing piece of this change.
- **Spec phase**: must include explicit scenarios for (a) admin DOCX, (b) admin PDF, (c) user PDF, (d) user DOCX → 403, (e) shared template → recipient-role enforcement, (f) Gotenberg-down on fresh generate → 503 + cleanup, (g) legacy doc lazy backfill on first request, (h) bulk admin `include_both`, (i) bulk non-admin `include_both` → 403.
- **Design phase**: must specify (a) the cleanup-on-failure transaction sketch, (b) the migration shape (rename + add nullable), (c) the exact placement of `can_download_format` calls (single point per endpoint), (d) the audit event schema for `DOCUMENT_DOWNLOAD`, (e) the sequential-vs-concurrent decision for bulk Gotenberg calls.
- **Spec and design can run in parallel** — they read the same proposal and tasks consumes both.
