from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from app.application.services import get_template_service
from app.application.services.template_service import TemplateService
from app.domain.exceptions import InvalidTemplateError, TemplateNotFoundError
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.template import (
    TemplateListResponse,
    TemplateResponse,
    TemplateUploadResponse,
    TemplateVersionResponse,
)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/upload", response_model=TemplateUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Upload a new .docx template."""
    # Validate file type
    if file.content_type not in ALLOWED_CONTENT_TYPES and not (
        file.filename and file.filename.endswith(".docx")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx files are accepted",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    try:
        template = await service.upload_template(
            name=name,
            file_bytes=file_bytes,
            file_size=len(file_bytes),
            tenant_id=str(current_user.tenant_id),
            created_by=str(current_user.user_id),
            description=description,
        )
    except InvalidTemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Build response from the ORM model returned by service
    return TemplateUploadResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        version=template.current_version,
        variables=template.versions[0].variables if template.versions else [],
        created_at=template.created_at,
    )


@router.post("/{template_id}/versions", response_model=TemplateUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_new_version(
    template_id: UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Upload a new version of an existing template."""
    # Validate file type
    if file.content_type not in ALLOWED_CONTENT_TYPES and not (
        file.filename and file.filename.endswith(".docx")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx files are accepted",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    try:
        result = await service.upload_new_version(
            template_id=str(template_id),
            file_bytes=file_bytes,
            file_size=len(file_bytes),
            tenant_id=str(current_user.tenant_id),
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    except InvalidTemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    template = result["template"]
    return TemplateUploadResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        version=result["new_version"],
        variables=result["variables"],
        created_at=template.created_at,
    )


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """List templates with pagination and optional search."""
    # Non-admin users only see their own templates
    created_by = None if current_user.role == "admin" else str(current_user.user_id)
    templates, total = await service.list_templates(
        page=page, size=size, search=search, created_by=created_by
    )

    items = []
    for t in templates:
        # Get variables from the current version
        current_vars: list[str] = []
        if t.versions:
            current_version = next(
                (v for v in t.versions if v.version == t.current_version), None
            )
            if current_version:
                current_vars = current_version.variables

        items.append(TemplateResponse(
            id=str(t.id),
            name=t.name,
            description=t.description,
            current_version=t.current_version,
            variables=current_vars,
            versions=[
                TemplateVersionResponse(
                    id=str(v.id),
                    version=v.version,
                    variables=v.variables,
                    file_size=v.file_size,
                    created_at=v.created_at,
                )
                for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
            ],
            created_at=t.created_at,
            updated_at=t.updated_at,
        ))

    return TemplateListResponse(items=items, total=total, page=page, size=size)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Get template detail with all versions."""
    try:
        t = await service.get_template(template_id)
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    current_vars: list[str] = []
    if t.versions:
        current_version = next(
            (v for v in t.versions if v.version == t.current_version), None
        )
        if current_version:
            current_vars = current_version.variables

    return TemplateResponse(
        id=str(t.id),
        name=t.name,
        description=t.description,
        current_version=t.current_version,
        variables=current_vars,
        versions=[
            TemplateVersionResponse(
                id=str(v.id),
                version=v.version,
                variables=v.variables,
                file_size=v.file_size,
                created_at=v.created_at,
            )
            for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
        ],
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Delete a template and all its versions."""
    try:
        await service.delete_template(template_id)
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
