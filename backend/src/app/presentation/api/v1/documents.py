from __future__ import annotations

import io
import uuid
import zipfile
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from app.application.services import get_document_service
from app.application.services.document_service import DocumentService
from app.domain.exceptions import (
    BulkLimitExceededError,
    DocumentNotFoundError,
    PdfConversionError,
    TemplateAccessDeniedError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)
from app.domain.services.permissions import (
    can_download_format,
    can_include_both_formats,
    can_view_all_documents,
)
from app.presentation.middleware.rate_limit import limiter, tier_limit_bulk, tier_limit_generate
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.document import (
    BulkGenerateResponse,
    DocumentListResponse,
    DocumentResponse,
    GenerateRequest,
)

router = APIRouter()

# MIME type constants
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_PDF_MIME = "application/pdf"
_ZIP_MIME = "application/zip"


@router.post("/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(tier_limit_generate)
async def generate_document(
    request: Request,
    body: GenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Generate a single document from a template version.

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
    except PdfConversionError:
        # REQ-DDF-05 / W-03: map to 503 — do NOT leak internal details
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de conversión a PDF no está disponible temporalmente. Por favor, intentá más tarde.",
        )

    doc = result["document"]
    return DocumentResponse(
        id=str(doc.id),
        template_version_id=str(doc.template_version_id),
        docx_file_name=doc.docx_file_name,
        pdf_file_name=doc.pdf_file_name,
        generation_type=doc.generation_type,
        status=doc.status,
        download_url=f"/documents/{doc.id}/download",
        variables_snapshot=doc.variables_snapshot,
        created_at=doc.created_at,
    )


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
        batch_id=batch_uuid, tenant_id=current_user.tenant_id
    )

    if not batch_docs:
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

    # Fetch document
    try:
        result = await service.get_document(document_id)
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
    """Delete a generated document and its file."""
    try:
        await service.delete_document(document_id)
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
    if can_view_all_documents(current_user.role):
        # Admin — no filter
        created_by = None
    elif template_id is not None:
        # Check if the current user owns this template
        owner_id = await service.get_template_owner_id(template_id)
        if owner_id == current_user.user_id:
            # Template owner — see all documents from this template
            created_by = None
        else:
            # Not the owner — only their own documents
            created_by = str(current_user.user_id)
    else:
        created_by = str(current_user.user_id)

    documents, total = await service.list_documents(page=page, size=size, template_id=template_id, created_by=created_by)

    items = [
        DocumentResponse(
            id=str(d.id),
            template_version_id=str(d.template_version_id),
            docx_file_name=d.docx_file_name,
            pdf_file_name=d.pdf_file_name,
            generation_type=d.generation_type,
            status=d.status,
            variables_snapshot=d.variables_snapshot,
            created_at=d.created_at,
        )
        for d in documents
    ]

    return DocumentListResponse(items=items, total=total, page=page, size=size)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Get document detail with fresh presigned download URL."""
    try:
        result = await service.get_document(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc = result["document"]
    return DocumentResponse(
        id=str(doc.id),
        template_version_id=str(doc.template_version_id),
        docx_file_name=doc.docx_file_name,
        pdf_file_name=doc.pdf_file_name,
        generation_type=doc.generation_type,
        status=doc.status,
        download_url=f"/documents/{doc.id}/download",
        variables_snapshot=doc.variables_snapshot,
        created_at=doc.created_at,
    )
