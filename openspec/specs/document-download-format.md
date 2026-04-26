# Capability: document-download-format

## Purpose

This capability covers the end-to-end ability for users to download a generated document in PDF or DOCX format, enforced by role-based access control. It includes: the `Document` entity schema change (dual file fields), the Alembic migration, mandatory dual-format generation on every `generate*` call, atomic failure semantics, role-gated download endpoints, lazy backfill for legacy documents, bulk download with format and `include_both` controls, sharing inheritance of recipient role, audit logging for every download and generation event, quota counting, and the frontend role-aware download UI.

## Requirements

### REQ-DDF-01: Document entity dual file fields

The `Document` entity MUST have `docx_file_name: str` and `pdf_file_name: str | None`. It MUST also have `docx_minio_path: str` and `pdf_minio_path: str | None`. The legacy fields `file_name` and `minio_path` MUST be renamed to their `docx_*` counterparts. `pdf_file_name` and `pdf_minio_path` are nullable to accommodate legacy rows; service layer MUST treat them as required for any newly generated document.

### REQ-DDF-02: Alembic migration 010_pdf_export

`backend/alembic/versions/010_pdf_export.py` MUST rename the existing `file_name` column to `docx_file_name` and `minio_path` to `docx_minio_path`. It MUST add `pdf_file_name VARCHAR NULL` and `pdf_minio_path VARCHAR NULL`. The migration MUST be reversible (downgrade renames back and drops the added columns). No NOT NULL backfill MUST be performed at migration time; `pdf_file_name IS NULL` is the sentinel for legacy rows.

### REQ-DDF-03: Generation always produces both formats

`POST /documents/generate` MUST always generate and persist both DOCX and PDF before returning. The request body MUST NOT accept an `output_format` parameter; its presence MUST result in HTTP 422. A single `Document` row is created with both `docx_file_name` and `pdf_file_name` populated.

### REQ-DDF-04: Bulk generation always produces both formats

`POST /documents/generate-bulk` MUST always generate and persist both DOCX and PDF per row. Bulk ZIP packaging for download is a separate concern (see REQ-DDF-12). The `output_format` parameter MUST NOT be accepted; its presence MUST result in HTTP 422.

### REQ-DDF-05: Atomic failure on PDF conversion error

If `PdfConverter.convert()` raises `PdfConversionError` during any `generate*` call, the entire operation MUST fail atomically: any DOCX object already uploaded to MinIO MUST be deleted, no `Document` row MUST be persisted, and the API MUST respond HTTP 503 with details from `PdfConversionError`. There MUST be no partial-success state observable to the caller.

### REQ-DDF-06: Download endpoint requires format parameter

`GET /documents/{id}/download` MUST require a `format` query parameter accepting values `"pdf"` or `"docx"`. A missing or invalid `format` value MUST return HTTP 422.

### REQ-DDF-07: Download RBAC via can_download_format

`GET /documents/{id}/download` MUST call `can_download_format(current_user.role, format)` before serving any file. A `False` return MUST result in HTTP 403 with a non-leaky message (e.g. "This format is not available for your role"). The endpoint MUST NOT serve file bytes before the RBAC check passes.

### REQ-DDF-08: can_download_format is the single RBAC decision point

`can_download_format(role: str, format: str) -> bool` MUST reside in `backend/src/app/domain/services/document_permissions.py`. It MUST use a `DOWNLOAD_FORMAT_PERMISSIONS: dict[str, frozenset[str]]` dict for its decisions. The default for any unrecognized role MUST be PDF-only (i.e. `frozenset({"pdf"})`). No other code path in the codebase MUST make an independent role-vs-format decision for downloads.

### REQ-DDF-09: Lazy backfill for legacy documents

When a request for `GET /documents/{id}/download?format=pdf` is received and the document has `pdf_file_name IS NULL`, the service MUST: fetch DOCX bytes from MinIO, call `PdfConverter.convert()`, upload the resulting PDF, update `Document.pdf_file_name` and `Document.pdf_minio_path`, and return the PDF bytes. The operation MUST be idempotent: subsequent requests for the same document find the persisted PDF and skip conversion. This applies regardless of the requester's role (both admin and non-admin may trigger backfill when requesting PDF).

### REQ-DDF-10: Lazy backfill failure semantics

If `PdfConverter.convert()` raises during backfill, the API MUST return HTTP 503. The `Document` row MUST NOT be updated (no partial write); `pdf_file_name` remains `NULL`. The DOCX in MinIO MUST NOT be deleted (it was not uploaded during this request).

### REQ-DDF-11: Bulk download RBAC

`GET /documents/bulk/{batch_id}/download` MUST accept `format=pdf|docx` and `include_both=true|false` query parameters. A non-admin user requesting `format=docx` MUST receive HTTP 403. A non-admin user requesting `include_both=true` MUST receive HTTP 403. Missing or invalid `format` MUST return HTTP 422.

### REQ-DDF-12: Bulk download with include_both

When an admin calls `GET /documents/bulk/{batch_id}/download?include_both=true`, the returned ZIP MUST contain both `<row_name>.docx` and `<row_name>.pdf` for each document in the batch. When `include_both=false` (default), the ZIP contains only the files matching the requested `format`.

### REQ-DDF-13: Sharing inherits recipient role

When a user accesses a document via a `template_shares` link or share-by-email flow and subsequently calls a download endpoint, `can_download_format(current_user.role, format)` MUST be evaluated against the **recipient's** role, not the sharer's. No special bypass MAY be granted by virtue of the document being shared.

### REQ-DDF-14: Generation audit log includes formats_generated

Every `AuditAction.DOCUMENT_GENERATE` and `AuditAction.DOCUMENT_GENERATE_BULK` event MUST include `details.formats_generated = ["docx", "pdf"]` for new documents. For legacy documents whose PDF was generated via backfill (i.e. the original generate event predates this change), the original event need not be retroactively updated; backfill itself does not write a new generate event.

### REQ-DDF-15: Download audit log

Every successful download via `GET /documents/{id}/download` and `GET /documents/bulk/{batch_id}/download` MUST write an audit event with `action = AuditAction.DOCUMENT_DOWNLOAD` and `details = {"format": <format>, "document_id": <id>, "via": "direct" | "share"}`. The `"via"` field MUST be `"share"` when the download is performed by a user who accessed the document through a `template_shares` or share-by-email path.

### REQ-DDF-16: Quota counts one per logical operation

A single `generate*` call producing both DOCX and PDF MUST increment the tenant's `monthly_document_limit` counter by exactly 1. Dual-format output MUST NOT be counted as 2 documents.

### REQ-DDF-17: Frontend role-aware single-document download UI

The frontend download control for a single document MUST render differently based on the authenticated user's role:
- Admin: a split-button with a caret opening a dropdown menu containing "Descargar como PDF" and "Descargar como Word".
- Non-admin: a single plain button "Descargar PDF" with no caret, no dropdown, and no Word option rendered (not merely disabled — not in the DOM).

### REQ-DDF-18: Frontend bulk download admin checkbox

The bulk download UI MUST show an "Incluir documentos Word" checkbox ONLY to admin users. When checked, the checkbox state MUST be passed as `include_both=true` in the bulk download query parameter. Non-admin users MUST NOT see the checkbox.

### REQ-DDF-19: Admin DOCX download regression safety

An admin user downloading a document with `format=docx` via any endpoint MUST receive the DOCX file with HTTP 200 and the correct MIME type (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`). This behavior MUST be identical to the pre-change DOCX-only flow.

## Scenarios

### SCEN-DDF-01: Admin generates and downloads DOCX
**Given**: An authenticated admin user
**When**: `POST /documents/generate` is called, then `GET /documents/{id}/download?format=docx` is called
**Then**: Both `docx_file_name` and `pdf_file_name` are populated on the `Document` row
**And**: The download returns HTTP 200 with DOCX content and correct MIME type
*(satisfies REQ-DDF-01, REQ-DDF-03, REQ-DDF-07, REQ-DDF-19)*

### SCEN-DDF-02: Admin generates, user downloads PDF
**Given**: An admin generates a document; an authenticated non-admin user has access
**When**: `GET /documents/{id}/download?format=pdf` is called by the non-admin user
**Then**: HTTP 200 is returned with PDF bytes and `Content-Type: application/pdf`
**And**: An audit event with `action=DOCUMENT_DOWNLOAD`, `details.format="pdf"`, `details.via="direct"` is written
*(satisfies REQ-DDF-07, REQ-DDF-15)*

### SCEN-DDF-03: Non-admin requests DOCX
**Given**: An authenticated non-admin user
**When**: `GET /documents/{id}/download?format=docx` is called
**Then**: HTTP 403 is returned with a non-leaky error message
**And**: No file bytes are returned; no audit download event is written for the denied attempt
*(satisfies REQ-DDF-07, REQ-DDF-08)*

### SCEN-DDF-04: Generation with output_format parameter rejected
**Given**: Any authenticated user
**When**: `POST /documents/generate` is called with `output_format` in the request body
**Then**: HTTP 422 is returned
*(satisfies REQ-DDF-03)*

### SCEN-DDF-05: Gotenberg down during generation — atomic rollback
**Given**: Gotenberg is unavailable; an admin calls `POST /documents/generate`
**When**: The DOCX upload to MinIO succeeds but `PdfConverter.convert()` raises `PdfConversionError`
**Then**: HTTP 503 is returned with error details
**And**: The DOCX object is deleted from MinIO; no `Document` row exists in the database
*(satisfies REQ-DDF-05)*

### SCEN-DDF-06: Legacy document — user requests PDF, backfill triggers
**Given**: A `Document` row with `pdf_file_name IS NULL` (legacy)
**When**: A non-admin user calls `GET /documents/{id}/download?format=pdf`
**Then**: The service converts the DOCX to PDF via `PdfConverter`, uploads it, updates `Document.pdf_file_name`
**And**: HTTP 200 is returned with PDF bytes; a subsequent request skips conversion and serves the persisted PDF
*(satisfies REQ-DDF-09)*

### SCEN-DDF-07: Legacy document — Gotenberg down during backfill
**Given**: A `Document` with `pdf_file_name IS NULL`; Gotenberg is unavailable
**When**: `GET /documents/{id}/download?format=pdf` is called
**Then**: HTTP 503 is returned; `Document.pdf_file_name` remains `NULL`
**And**: The DOCX in MinIO is not deleted
*(satisfies REQ-DDF-10)*

### SCEN-DDF-08: Legacy document — admin requests DOCX (no backfill needed)
**Given**: A `Document` with `pdf_file_name IS NULL`
**When**: An admin calls `GET /documents/{id}/download?format=docx`
**Then**: HTTP 200 is returned with DOCX bytes; no PDF conversion is attempted
*(satisfies REQ-DDF-09, REQ-DDF-19)*

### SCEN-DDF-09: Bulk admin download — PDF only
**Given**: An authenticated admin with a completed bulk batch
**When**: `GET /documents/bulk/{batch_id}/download?format=pdf&include_both=false` is called
**Then**: HTTP 200 is returned with a ZIP containing only `<name>.pdf` files
*(satisfies REQ-DDF-11, REQ-DDF-12)*

### SCEN-DDF-10: Bulk admin download — include_both=true
**Given**: An authenticated admin with a completed bulk batch
**When**: `GET /documents/bulk/{batch_id}/download?format=pdf&include_both=true` is called
**Then**: HTTP 200 is returned with a ZIP containing both `<name>.docx` and `<name>.pdf` for each row
*(satisfies REQ-DDF-11, REQ-DDF-12)*

### SCEN-DDF-11: Bulk non-admin download — format=docx rejected
**Given**: An authenticated non-admin user with a completed bulk batch
**When**: `GET /documents/bulk/{batch_id}/download?format=docx` is called
**Then**: HTTP 403 is returned
*(satisfies REQ-DDF-11)*

### SCEN-DDF-12: Bulk non-admin download — include_both=true rejected
**Given**: An authenticated non-admin user
**When**: `GET /documents/bulk/{batch_id}/download?format=pdf&include_both=true` is called
**Then**: HTTP 403 is returned (loud rejection, not silent coercion)
*(satisfies REQ-DDF-11)*

### SCEN-DDF-13: Shared document — recipient cannot bypass RBAC for DOCX
**Given**: An admin shared a template with a non-admin user; the non-admin generated a document via the share
**When**: The non-admin user calls `GET /documents/{id}/download?format=docx`
**Then**: HTTP 403 is returned — same as REQ-DDF-03, regardless of the share relationship
*(satisfies REQ-DDF-13)*

### SCEN-DDF-14: Shared document — recipient downloads PDF, audit records via=share
**Given**: An admin shared a template with a non-admin user; a document was generated via the share
**When**: The non-admin user calls `GET /documents/{id}/download?format=pdf` through the share-by-email or template_shares path
**Then**: HTTP 200 is returned with PDF bytes
**And**: Audit event written with `details.via="share"`, `details.format="pdf"`
*(satisfies REQ-DDF-13, REQ-DDF-15)*

### SCEN-DDF-15: Generation audit and quota
**Given**: An admin calls `POST /documents/generate` successfully
**When**: The response returns HTTP 200
**Then**: The audit log contains `action=DOCUMENT_GENERATE` with `details.formats_generated=["docx","pdf"]`
**And**: The tenant's `monthly_document_limit` counter is incremented by exactly 1
*(satisfies REQ-DDF-14, REQ-DDF-16)*

### SCEN-DDF-16: can_download_format truth table
**Given**: The `can_download_format` function from `document_permissions.py`
**When**: Called with each of the following: `("admin","docx")`, `("admin","pdf")`, `("user","docx")`, `("user","pdf")`, `("unknown_role","docx")`, `("unknown_role","pdf")`
**Then**: Results are `True`, `True`, `False`, `True`, `False`, `True` respectively
*(satisfies REQ-DDF-08)*
