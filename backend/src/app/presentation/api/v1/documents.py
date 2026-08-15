from __future__ import annotations

import io
import unicodedata
import uuid
import zipfile
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from app.application.services import get_document_service
from app.application.services.document_service import DocumentService
from app.domain.exceptions import (
    BulkLimitExceededError,
    ComputedVariableError,
    DocumentNotFoundError,
    InvalidSpreadsheetError,
    PdfConversionError,
    TemplateAccessDeniedError,
    TemplateRenderError,
    TemplateVersionFileNotFoundError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)
from app.domain.services.permissions import (
    can_download_format,
    can_include_both_formats,
    can_view_all_documents,
)
from app.presentation.middleware.rate_limit import (
    limiter,
    tier_limit_bulk,
    tier_limit_generate,
    tier_limit_preview,
)
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.document import (
    BulkGenerateResponse,
    DocumentGroupListResponse,
    DocumentGroupResponse,
    DocumentListResponse,
    DocumentResponse,
    GenerateRequest,
    GenerateResponse,
    PreviewRequest,
)

router = APIRouter()

# MIME type constants
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME = "application/pdf"
_ZIP_MIME = "application/zip"


def _to_document_response(doc, download_url: str | None = None) -> DocumentResponse:
    """Build a DocumentResponse from an enriched domain Document.

    The repository populates template_id / template_name / template_version
    via the template_versions → templates join (the FK is NOT NULL, so the
    values are always concrete).
    """
    return DocumentResponse(
        id=str(doc.id),
        template_version_id=str(doc.template_version_id),
        template_id=str(doc.template_id),
        template_name=doc.template_name,
        template_version=doc.template_version,
        docx_file_name=doc.docx_file_name,
        pdf_file_name=doc.pdf_file_name,
        generation_type=doc.generation_type,
        status=doc.status,
        download_url=download_url,
        variables_snapshot=doc.variables_snapshot,
        created_at=doc.created_at,
        group_id=str(doc.group_id) if doc.group_id else None,
        related_label=doc.related_label,
    )


def _content_disposition_attachment(filename: str) -> str:
    """Build a safe ``Content-Disposition: attachment`` header value.

    Emits an ASCII-safe ``filename`` fallback PLUS the exact UTF-8 name in an
    RFC 5987 ``filename*`` parameter (same shape as the template download
    endpoints), so a crafted template name can never forge headers.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_fallback = (
        "".join(c for c in ascii_name if c.isprintable() and c not in '"\\')
        or "download.zip"
    )
    return (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


def _to_document_group_response(docs) -> DocumentGroupResponse:
    """Build a DocumentGroupResponse from a group's documents.

    `docs` is expected primary-first in render order (group_position asc). The
    primary is the group_position 0 document (fallback: the first document,
    which is already ordered by created_at,id); the rest are the related files.
    """
    primary_doc = next((d for d in docs if d.group_position == 0), docs[0])
    related_docs = [d for d in docs if d is not primary_doc]
    group_id = primary_doc.group_id
    return DocumentGroupResponse(
        group_id=str(group_id) if group_id else None,
        primary=_to_document_response(primary_doc),
        related=[_to_document_response(d) for d in related_docs],
    )


async def _resolve_created_by_scope(
    service: DocumentService, current_user: CurrentUser, template_id: str | None
) -> str | None:
    """Resolve the REQ-OWN-DOCS `created_by` scope for a document listing.

    Single source of truth shared by the flat list and the grouped list so the
    two can never drift:
      * admin  → None (sees everything)
      * template owner (when template_id given) → None (sees all docs of that
        template)
      * everyone else → their own user id
    """
    if can_view_all_documents(current_user.role):
        return None
    if template_id is not None:
        owner_id = await service.get_template_owner_id(template_id)
        if owner_id == current_user.user_id:
            return None
        return str(current_user.user_id)
    return str(current_user.user_id)


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(tier_limit_generate)
async def generate_document(
    request: Request,
    body: GenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Generate documents from a template version — the primary docx plus
    every related file of the version, filled with ONE shared variable set.

    Response: {"documents": [DocumentResponse, ...], "group_id": str|null} —
    primary first, then related files by position. group_id is null when the
    version has no related files (the list then has one element).

    REQ-DDF-03: output_format is NOT accepted (GenerateRequest has extra="forbid").
    REQ-DDF-05: PdfConversionError → HTTP 503 (atomic rollback already done in service).
    Per REQ-SOS-13: _require_verified_email removed (single-org-cutover).
    """
    try:
        result = await service.generate_single(
            template_version_id=body.template_version_id,
            variables=body.variables,
            tenant_id=str(current_user.tenant_id),
            created_by=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template version not found")
    except ComputedVariableError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TemplateRenderError:
        # SSTI containment: an unsafe/unsupported Jinja expression in the
        # template was blocked by the sandbox. Map to a non-leaking 422.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La plantilla contiene una expresión no compatible o no permitida y no pudo ser procesada.",
        )
    except PdfConversionError:
        # REQ-DDF-05 / W-03: map to 503 — do NOT leak internal details
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de conversión a PDF no está disponible temporalmente. Por favor, intentá más tarde.",
        )

    group_id = result["group_id"]
    return GenerateResponse(
        documents=[
            _to_document_response(doc, download_url=f"/documents/{doc.id}/download")
            for doc in result["documents"]
        ],
        group_id=str(group_id) if group_id else None,
    )


@router.post("/preview")
@limiter.limit(tier_limit_preview)
async def preview_document(
    request: Request,
    body: PreviewRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Render a true-fidelity PDF preview from the CURRENT (possibly partial)
    variable values. Nothing is persisted — no MinIO uploads, no Document
    row, no usage/audit tracking, no quota check.

    `file_id` (optional) previews a RELATED file of the version instead of
    the primary docx.

    Missing variables render as blanks (docxtpl default Jinja2 Undefined).
    """
    try:
        pdf_bytes = await service.preview(
            template_version_id=body.template_version_id,
            variables=body.variables,
            user_id=str(current_user.user_id),
            role=current_user.role,
            file_id=body.file_id,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo relacionado no encontrado",
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template version not found")
    except ComputedVariableError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TemplateRenderError:
        # SSTI containment: an unsafe/unsupported Jinja expression in the
        # template was blocked by the sandbox. Map to a non-leaking 422.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La plantilla contiene una expresión no compatible o no permitida y no pudo ser procesada.",
        )
    except PdfConversionError:
        # REQ-DDF-05: PdfConversionError → HTTP 503 — same mapping as the
        # other document endpoints.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de conversión a PDF no está disponible temporalmente. Por favor, intentá más tarde.",
        )

    return Response(content=pdf_bytes, media_type=_PDF_MIME)


@router.get("/excel-template/{template_version_id}")
async def get_excel_template(
    template_version_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download a blank Excel template with variable columns for bulk generation."""
    try:
        excel_bytes, filename = await service.generate_excel_template(
            template_version_id,
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template version not found")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-bulk", status_code=status.HTTP_201_CREATED)
@limiter.limit(tier_limit_bulk)
async def generate_bulk(
    request: Request,
    template_version_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Generate multiple documents from a filled Excel file.

    REQ-DDF-04: output_format is NOT accepted in the body.
    REQ-DDF-05 / W-04: PdfConversionError → HTTP 503.
    W-05: errors field is always [] on success (breaking change from partial-failure model).
    Per REQ-SOS-13: _require_verified_email removed (single-org-cutover).
    """
    # REQ-DDF-04: output_format must not be accepted in the multipart body.
    # FastAPI silently ignores unexpected form fields, so we explicitly inspect
    # the raw form data and reject if 'output_format' is present.
    form = await request.form()
    if "output_format" in form:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The 'output_format' field is not accepted; both formats are always generated.",
        )

    # Validate file type
    if not (file.filename and file.filename.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")

    excel_bytes = await file.read()
    if len(excel_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse and validate Excel data
    try:
        rows = await service.parse_excel_data(
            template_version_id,
            excel_bytes,
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Template version not found")
    except InvalidSpreadsheetError as e:
        # Corrupt / non-.xlsx upload that passed the extension check — a
        # readable client error, not a server fault.
        raise HTTPException(status_code=400, detail=str(e))
    except BulkLimitExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except VariablesMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Generate documents
    try:
        result = await service.generate_bulk(
            template_version_id=template_version_id,
            rows=rows,
            tenant_id=str(current_user.tenant_id),
            created_by=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ComputedVariableError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TemplateRenderError:
        # SSTI containment: an unsafe/unsupported Jinja expression in the
        # template was blocked by the sandbox. Map to a non-leaking 422.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La plantilla contiene una expresión no compatible o no permitida y no pudo ser procesada.",
        )
    except PdfConversionError:
        # REQ-DDF-05 / W-04: atomic rollback already done in service — map to 503
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de conversión a PDF no está disponible temporalmente. Por favor, intentá más tarde.",
        )

    return BulkGenerateResponse(
        batch_id=str(result["batch_id"]),
        document_count=result["document_count"],
        download_url=f"/documents/bulk/{result['batch_id']}/download",
        errors=result["errors"],  # always [] on success (W-05 resolution)
    )


@router.get("/bulk/{batch_id}/download")
async def download_bulk(
    batch_id: str,
    format: Literal["pdf", "docx"] = Query(..., description="File format to download (pdf or docx)"),
    include_both: bool = Query(False, description="Include both .docx and .pdf files in the ZIP (admin only)"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download a ZIP of bulk-generated documents with format selection and RBAC.

    REQ-DDF-11: format=docx → 403 for non-admin; include_both=true → 403 for non-admin.
    REQ-DDF-12: include_both=true includes both .docx + .pdf per document.
    ADR-PDF-08: serial backfill for legacy rows when format includes PDF.
    REQ-DDF-15: DOCUMENT_DOWNLOAD audit event written.
    """
    # RBAC check — REQ-DDF-11
    if not can_download_format(current_user.role, format):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este formato de descarga no está disponible para tu rol.",
        )
    if include_both and not can_include_both_formats(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La opción de incluir ambos formatos solo está disponible para administradores.",
        )

    # Resolve batch_id as UUID
    try:
        batch_uuid = uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid batch_id format")

    # Fetch all documents for this batch from the repository via the public
    # delegating method (W-PRES-02 fix: replaces service._doc_repo private
    # access + O(N total tenant docs) full-scan with O(batch_size) query).
    batch_docs = await service.list_documents_by_batch(
        batch_id=batch_uuid,
        tenant_id=current_user.tenant_id,
        requester_id=current_user.user_id,
        role=current_user.role,
    )

    if not batch_docs:
        # Empty for a non-existent batch OR a batch owned by another user
        # (non-admin) — the 404 is non-leaking either way (finding #1).
        raise HTTPException(status_code=404, detail="Bulk download batch not found")

    # Build ZIP in memory — ADR-PDF-08 serial backfill
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in batch_docs:
            stem = doc.docx_file_name[:-5] if doc.docx_file_name.endswith(".docx") else doc.docx_file_name

            if include_both:
                # Include both DOCX and PDF for each document
                # Backfill PDF if needed (legacy row)
                if doc.pdf_file_name is None:
                    try:
                        doc = await service.ensure_pdf(doc.id)
                    except PdfConversionError:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="El servicio de conversión a PDF no está disponible temporalmente.",
                        )

                docx_bytes = await service.download_document(doc.docx_minio_path)
                pdf_bytes = await service.download_document(doc.pdf_minio_path)
                zf.writestr(f"{stem}.docx", docx_bytes)
                zf.writestr(f"{stem}.pdf", pdf_bytes)

            elif format == "pdf":
                # PDF only — backfill if legacy
                if doc.pdf_file_name is None:
                    try:
                        doc = await service.ensure_pdf(doc.id)
                    except PdfConversionError:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="El servicio de conversión a PDF no está disponible temporalmente.",
                        )
                pdf_bytes = await service.download_document(doc.pdf_minio_path)
                zf.writestr(f"{stem}.pdf", pdf_bytes)

            else:
                # DOCX only
                docx_bytes = await service.download_document(doc.docx_minio_path)
                zf.writestr(f"{stem}.docx", docx_bytes)

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.read()

    # Audit log — REQ-DDF-15
    await service.log_bulk_download_event(
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        batch_id=batch_uuid,
        format=format,
        via="direct",
        include_both=include_both,
    )

    return Response(
        content=zip_bytes,
        media_type=_ZIP_MIME,
        headers={"Content-Disposition": f'attachment; filename="bulk_{batch_id}.zip"'},
    )


@router.get("/groups", response_model=DocumentGroupListResponse)
async def list_document_groups(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    template_id: str | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """List generated documents grouped by generation, paginated by GROUP.

    Each item is a group: the primary document plus every related file that
    was rendered with the same variable set. A document from a version without
    related files is its own single-member group (group_id null, related []).

    REQ-OWN-DOCS: same scoping as GET /documents — admins see all; the
    template's owner (when template_id is given) sees all groups of that
    template; everyone else sees only their own.
    """
    created_by = await _resolve_created_by_scope(service, current_user, template_id)

    groups, total = await service.list_document_groups(
        page=page, size=size, template_id=template_id, created_by=created_by
    )

    items = [_to_document_group_response(g) for g in groups]

    return DocumentGroupListResponse(items=items, total=total, page=page, size=size)


@router.get("/groups/{group_id}/download")
async def download_group(
    group_id: str,
    format: Literal["pdf", "docx"] = Query(..., description="File format to download (pdf or docx)"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download a single ZIP with every document of a group in one format.

    Streams application/zip named ``{sanitized_template_name}_paquete.zip``.
    Contains the primary + related documents in the requested format
    (primary-first, each named by its docx_file_name / pdf_file_name).

    RBAC: format follows can_download_format (non-admin → PDF only; docx → 403,
    same contract as the single-document download). Ownership: creator-or-admin
    via the same rule as the other download paths — an empty / foreign group is
    a non-leaking 404.

    PDF backfill is intentionally NOT performed here (group members are always
    produced dual-format). A member missing a PDF is skipped best-effort rather
    than triggering a 503, so one legacy row can never fail the whole download.
    """
    # RBAC — same format gate as the single-document download.
    if not can_download_format(current_user.role, format):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este formato de descarga no está disponible para tu rol.",
        )

    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid group_id format")

    docs = await service.list_documents_by_group(
        group_id=group_uuid,
        tenant_id=current_user.tenant_id,
        requester_id=current_user.user_id,
        role=current_user.role,
    )

    if not docs:
        # Empty for a non-existent group OR a group owned by another user
        # (non-admin) — non-leaking 404 either way (finding #1).
        raise HTTPException(status_code=404, detail="Document group not found")

    # Build ZIP in memory (primary-first order preserved from the repository).
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            if format == "pdf":
                # No backfill — skip a member that has no PDF (best-effort).
                if doc.pdf_file_name is None or doc.pdf_minio_path is None:
                    continue
                pdf_bytes = await service.download_document(doc.pdf_minio_path)
                zf.writestr(doc.pdf_file_name, pdf_bytes)
            else:
                docx_bytes = await service.download_document(doc.docx_minio_path)
                zf.writestr(doc.docx_file_name, docx_bytes)

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.read()

    # Filename from the (shared) template name, minimally sanitized.
    raw_name = docs[0].template_name or "documentos"
    safe_name = (
        "".join(c for c in raw_name if c.isalnum() or c in " _-").strip()
        or "documentos"
    )
    filename = f"{safe_name}_paquete.zip"

    # Audit best-effort (reuses DOCUMENT_DOWNLOAD with resource_type group).
    await service.log_group_download_event(
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        group_id=group_uuid,
        format=format,
        document_count=len(docs),
    )

    return Response(
        content=zip_bytes,
        media_type=_ZIP_MIME,
        headers={"Content-Disposition": _content_disposition_attachment(filename)},
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    format: Literal["pdf", "docx"] = Query(..., description="File format to download (pdf or docx)"),
    via: Literal["direct", "share"] = Query("direct", description="Download context for audit trail"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download a generated document in the requested format.

    REQ-DDF-06: format param is required (Literal["pdf","docx"]).
    REQ-DDF-07: RBAC via can_download_format before serving any bytes.
    REQ-DDF-09: PDF backfill (ensure_pdf) for legacy rows when format=pdf.
    REQ-DDF-15: DOCUMENT_DOWNLOAD audit event with format + via.
    ADR-PDF-07: via=share sanity check — creator's own download → override to "direct".
    """
    # RBAC check — REQ-DDF-07 / REQ-DDF-08
    if not can_download_format(current_user.role, format):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este formato de descarga no está disponible para tu rol.",
        )

    # Fetch document — ownership enforced in the service (finding #1): a
    # non-creator non-admin gets DocumentNotFoundError -> non-leaking 404.
    try:
        result = await service.get_document(
            document_id,
            requester_id=current_user.user_id,
            role=current_user.role,
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc = result["document"]

    if format == "pdf":
        # Lazy backfill for legacy docs (REQ-DDF-09)
        if doc.pdf_file_name is None:
            try:
                doc = await service.ensure_pdf(document_id)
            except PdfConversionError:
                # REQ-DDF-10 / W-03: 503, doc row unchanged
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="El servicio de conversión a PDF no está disponible temporalmente. Por favor, intentá más tarde.",
                )

        file_bytes = await service.download_document(doc.pdf_minio_path)
        media_type = _PDF_MIME
        filename = doc.pdf_file_name or (doc.docx_file_name[:-5] + ".pdf")

    else:
        # DOCX download — no backfill needed
        file_bytes = await service.download_document(doc.docx_minio_path)
        media_type = _DOCX_MIME
        filename = doc.docx_file_name

    # ADR-PDF-07: via=share sanity check — if current_user IS the document creator,
    # override via to "direct" to prevent audit spoofing.
    effective_via = via
    if via == "share" and current_user.user_id == doc.created_by:
        effective_via = "direct"

    # Audit log — REQ-DDF-15
    await service.log_download_event(
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        document_id=document_id,
        format=format,
        via=effective_via,
    )

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Delete a generated document and its file.

    Ownership is enforced in the service (finding #1): a non-creator non-admin
    gets DocumentNotFoundError -> non-leaking 404, and the document is left
    untouched.
    """
    try:
        await service.delete_document(
            document_id,
            requester_id=current_user.user_id,
            role=current_user.role,
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    template_id: str | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """List generated documents with pagination.

    REQ-OWN-DOCS: When template_id is provided, the template's owner sees all
    documents from that template (bypasses created_by filter).  Admins always
    see everything.  All other users see only their own documents.
    """
    created_by = await _resolve_created_by_scope(service, current_user, template_id)

    documents, total = await service.list_documents(page=page, size=size, template_id=template_id, created_by=created_by)

    items = [_to_document_response(d) for d in documents]

    return DocumentListResponse(items=items, total=total, page=page, size=size)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Get document detail with fresh presigned download URL.

    Ownership is enforced in the service (finding #1): a non-creator non-admin
    gets DocumentNotFoundError -> non-leaking 404.
    """
    try:
        result = await service.get_document(
            document_id,
            requester_id=current_user.user_id,
            role=current_user.role,
        )
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc = result["document"]
    return _to_document_response(doc, download_url=f"/documents/{doc.id}/download")
