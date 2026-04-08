from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.application.services import get_template_service
from app.application.services.template_service import TemplateService
from app.domain.exceptions import (
    DomainError,
    InvalidTemplateError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
    TemplateSharingError,
)
from app.infrastructure.templating import get_template_engine
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.template import (
    ShareTemplateRequest,
    TemplateListResponse,
    TemplateResponse,
    TemplateShareResponse,
    TemplateUploadResponse,
    TemplateVersionResponse,
)

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _validate_docx_upload(file: UploadFile) -> None:
    """Raise HTTPException if the uploaded file is not a .docx."""
    if file.content_type not in ALLOWED_CONTENT_TYPES and not (
        file.filename and file.filename.endswith(".docx")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos .docx",
        )


@router.post("/validate")
async def validate_template(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Validate a .docx template without uploading it."""
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    engine = get_template_engine()
    return await engine.validate(file_bytes)


@router.post("/auto-fix")
async def auto_fix_template(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Auto-fix fixable issues in a .docx template and return the corrected file."""
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    engine = get_template_engine()
    fixed_bytes = await engine.auto_fix(file_bytes)

    filename = file.filename or "template_corregido.docx"
    if not filename.endswith("_corregido.docx"):
        filename = filename.replace(".docx", "_corregido.docx")

    return Response(
        content=fixed_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/upload", response_model=TemplateUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Upload a new .docx template."""
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    # Validate template before upload
    engine = get_template_engine()
    validation = await engine.validate(file_bytes)

    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "La plantilla tiene errores que deben corregirse antes de subirla.",
                "validation": validation,
            },
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
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    # Validate template before upload
    engine = get_template_engine()
    validation = await engine.validate(file_bytes)

    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "La plantilla tiene errores que deben corregirse antes de subirla.",
                "validation": validation,
            },
        )

    try:
        result = await service.upload_new_version(
            template_id=str(template_id),
            file_bytes=file_bytes,
            file_size=len(file_bytes),
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    templates, total = await service.list_templates(
        page=page,
        size=size,
        search=search,
        user_id=current_user.user_id,
        role=current_user.role,
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

        access_type = getattr(t, "access_type", "owned")
        is_owner = str(getattr(t, "created_by", "")) == str(current_user.user_id)

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
                    variables_meta=v.variables_meta or [],
                    file_size=v.file_size,
                    created_at=v.created_at,
                )
                for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
            ],
            created_at=t.created_at,
            updated_at=t.updated_at,
            access_type=access_type,
            is_owner=is_owner,
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
        t = await service.get_template(
            template_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
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

    is_owner = str(getattr(t, "created_by", "")) == str(current_user.user_id)
    access_type = "owned" if is_owner else ("admin" if current_user.role == "admin" else "shared")

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
                variables_meta=v.variables_meta or [],
                file_size=v.file_size,
                created_at=v.created_at,
            )
            for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
        ],
        created_at=t.created_at,
        updated_at=t.updated_at,
        access_type=access_type,
        is_owner=is_owner,
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Delete a template and all its versions."""
    try:
        await service.delete_template(
            template_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plantilla no encontrada",
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/{template_id}/shares", response_model=TemplateShareResponse, status_code=status.HTTP_201_CREATED)
async def share_template(
    template_id: UUID,
    body: ShareTemplateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Share a template with another user (owner/admin only)."""
    try:
        share = await service.share_template(
            template_id=template_id,
            user_id=body.user_id,
            current_user_id=current_user.user_id,
            role=current_user.role,
            tenant_id=current_user.tenant_id,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateSharingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return TemplateShareResponse(
        id=str(share.id),
        template_id=str(share.template_id),
        user_id=str(share.user_id),
        tenant_id=str(share.tenant_id),
        shared_by=str(share.shared_by),
        shared_at=share.shared_at,
    )


@router.delete("/{template_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unshare_template(
    template_id: UUID,
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Revoke a user's access to a template (owner/admin only)."""
    try:
        await service.unshare_template(
            template_id=template_id,
            user_id=user_id,
            current_user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")


@router.get("/{template_id}/shares", response_model=list[TemplateShareResponse])
async def list_template_shares(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """List all shares for a template (accessible to owner, shared users, or admin)."""
    try:
        shares = await service.list_template_shares(
            template_id=template_id,
            current_user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return [
        TemplateShareResponse(
            id=str(s.id),
            template_id=str(s.template_id),
            user_id=str(s.user_id),
            tenant_id=str(s.tenant_id),
            shared_by=str(s.shared_by),
            shared_at=s.shared_at,
        )
        for s in shares
    ]
