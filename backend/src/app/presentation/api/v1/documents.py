from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.application.services import get_document_service
from app.application.services.document_service import DocumentService
from app.domain.exceptions import (
    BulkLimitExceededError,
    DocumentNotFoundError,
    TemplateVersionNotFoundError,
    VariablesMismatchError,
)
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.document import (
    BulkGenerateResponse,
    DocumentListResponse,
    DocumentResponse,
    GenerateRequest,
)

router = APIRouter()


@router.post("/generate", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def generate_document(
    request: GenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Generate a single document from a template version."""
    try:
        result = await service.generate_single(
            template_version_id=request.template_version_id,
            variables=request.variables,
            tenant_id=str(current_user.tenant_id),
            created_by=str(current_user.user_id),
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template version not found")

    doc = result["document"]
    return DocumentResponse(
        id=str(doc.id),
        template_version_id=str(doc.template_version_id),
        file_name=doc.file_name,
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
        excel_bytes, filename = await service.generate_excel_template(template_version_id)
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template version not found")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/generate-bulk", status_code=status.HTTP_201_CREATED)
async def generate_bulk(
    template_version_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Generate multiple documents from a filled Excel file."""
    # Validate file type
    if not (file.filename and file.filename.endswith(".xlsx")):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")

    excel_bytes = await file.read()
    if len(excel_bytes) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse and validate Excel data
    try:
        rows = await service.parse_excel_data(template_version_id, excel_bytes)
    except TemplateVersionNotFoundError:
        raise HTTPException(status_code=404, detail="Template version not found")
    except BulkLimitExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except VariablesMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Generate documents
    result = await service.generate_bulk(
        template_version_id=template_version_id,
        rows=rows,
        tenant_id=str(current_user.tenant_id),
        created_by=str(current_user.user_id),
    )

    return BulkGenerateResponse(
        batch_id=str(result["batch_id"]),
        document_count=result["document_count"],
        download_url=f"/documents/bulk/{result['batch_id']}/download",
        errors=result["errors"],
    )


@router.get("/bulk/{batch_id}/download")
async def download_bulk(
    batch_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download the ZIP file for a bulk generation batch."""
    zip_path = f"{current_user.tenant_id}/{batch_id}/bulk.zip"
    try:
        zip_bytes = await service.download_document(zip_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Bulk download not found")

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="bulk_{batch_id}.zip"'},
    )


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Download a generated document file."""
    try:
        result = await service.get_document(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc = result["document"]
    file_bytes = await service.download_document(doc.minio_path)

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.file_name}"',
        },
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
    """List generated documents with pagination."""
    created_by = None if current_user.role == "admin" else str(current_user.user_id)
    documents, total = await service.list_documents(page=page, size=size, template_id=template_id, created_by=created_by)

    items = [
        DocumentResponse(
            id=str(d.id),
            template_version_id=str(d.template_version_id),
            file_name=d.file_name,
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
        file_name=doc.file_name,
        generation_type=doc.generation_type,
        status=doc.status,
        download_url=f"/documents/{doc.id}/download",
        variables_snapshot=doc.variables_snapshot,
        created_at=doc.created_at,
    )
