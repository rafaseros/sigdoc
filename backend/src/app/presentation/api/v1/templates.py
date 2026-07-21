import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.application.services import (
    get_template_preset_service,
    get_template_service,
    get_user_repository,
)
from app.application.services.template_preset_service import TemplatePresetService
from app.application.services.template_service import TemplateService
from app.domain.exceptions import (
    ComputedVariableValidationError,
    DomainError,
    InvalidTemplateError,
    InvalidVariableMappingError,
    MappingTextNotFoundError,
    TemplateAccessDeniedError,
    TemplateFolderNotFoundError,
    TemplateNotFoundError,
    TemplatePresetNotFoundError,
    TemplateSharingError,
    TemplateVersionFileNotFoundError,
    TemplateVersionNotFoundError,
)
from app.domain.ports.user_repository import UserRepository
from app.domain.services.permissions import can_view_all_templates
from app.infrastructure.templating import get_template_engine
from app.presentation.api.dependencies import require_template_manager
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.preset import (
    PresetCreateRequest,
    PresetListResponse,
    PresetResponse,
    PresetUpdateRequest,
)
from app.presentation.schemas.template import (
    ShareTemplateRequest,
    TemplateAnalyzeExampleResponse,
    TemplateListResponse,
    TemplateResponse,
    TemplateShareResponse,
    TemplateStructureResponse,
    TemplateUpdateRequest,
    TemplateUploadResponse,
    TemplateVersionFileResponse,
    TemplateVersionResponse,
    UpdateVariableTypesRequest,
    VariableMappingsPayload,
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


def _file_to_response(f) -> TemplateVersionFileResponse:
    """Build a TemplateVersionFileResponse from a domain entity / ORM model."""
    return TemplateVersionFileResponse(
        id=str(f.id),
        label=f.label,
        variables=list(f.variables or []),
        file_size=f.file_size,
        position=f.position,
        created_at=f.created_at,
    )


def _version_to_response(v) -> TemplateVersionResponse:
    """Build a TemplateVersionResponse (incl. related files) from a domain
    entity / ORM model."""
    files = sorted(
        list(getattr(v, "files", []) or []), key=lambda f: f.position
    )
    return TemplateVersionResponse(
        id=str(v.id),
        version=v.version,
        variables=v.variables,
        variables_meta=v.variables_meta or [],
        file_size=v.file_size,
        created_at=v.created_at,
        files=[_file_to_response(f) for f in files],
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
    current_user: CurrentUser = Depends(require_template_manager),
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


@router.post("/analyze-example", response_model=TemplateAnalyzeExampleResponse)
async def analyze_example(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Extract the document structure of a filled example .docx (no storage).

    First step of the template-from-example flow: the user uploads a real
    document (no placeholders required), sees its content, and marks literal
    text spans as variables. Same auth and file validation as /validate.
    """
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    try:
        structure = await service.analyze_example(file_bytes)
    except InvalidTemplateError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return TemplateAnalyzeExampleResponse(
        structure=TemplateStructureResponse(**structure)
    )


@router.post(
    "/from-example",
    response_model=TemplateUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_from_example(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    mappings: str = Form(...),
    current_user: CurrentUser = Depends(require_template_manager),
    service: TemplateService = Depends(get_template_service),
):
    """Create a template v1 from a filled example .docx.

    `mappings` is a JSON string array of {"text", "variable"} items. The
    backend replaces every literal occurrence with {{ placeholders }} without
    altering Word formatting, then runs the standard upload pipeline on the
    rewritten bytes. Same auth as /upload; same error contract (400 invalid
    file, 409 name collision) plus 422 for invalid mappings or texts not
    found in the document.
    """
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    # Parse + validate the mappings JSON form field
    import json

    from pydantic import ValidationError

    try:
        raw_mappings = json.loads(mappings)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo 'mappings' debe ser un arreglo JSON válido de objetos {text, variable}",
        )
    try:
        payload = VariableMappingsPayload(mappings=raw_mappings)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Mappings inválidos",
                "errors": [
                    f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                    for err in e.errors()
                ],
            },
        )

    try:
        template = await service.create_template_from_example(
            name=name,
            file_bytes=file_bytes,
            mappings=[m.model_dump() for m in payload.mappings],
            tenant_id=str(current_user.tenant_id),
            created_by=str(current_user.user_id),
            description=description,
        )
    except MappingTextNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(e),
                "missing_texts": e.missing_texts,
            },
        )
    except InvalidVariableMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
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
    current_user: CurrentUser = Depends(require_template_manager),
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


async def _resolve_owner_name(
    user_repo: UserRepository, owner_id, cache: dict
) -> str | None:
    """Look up a template owner's full name, memoized per-request in `cache`.

    Templates commonly share the same owner (e.g. a list page), so this
    avoids repeating identical lookups within a single request.
    """
    key = str(owner_id)
    if key not in cache:
        owner = await user_repo.get_by_id(owner_id)
        cache[key] = owner.full_name if owner is not None else None
    return cache[key]


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    folder_id: str | None = Query(
        None,
        description="Filter by folder. A folder UUID filters to that folder; "
        "the literal string 'none' filters to unfiled templates.",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """List templates with pagination and optional search/folder filter."""
    folder_filter_unfiled = False
    parsed_folder_id: UUID | None = None
    if folder_id is not None:
        if folder_id == "none":
            folder_filter_unfiled = True
        else:
            try:
                parsed_folder_id = UUID(folder_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="folder_id inválido",
                )

    templates, total = await service.list_templates(
        page=page,
        size=size,
        search=search,
        user_id=current_user.user_id,
        role=current_user.role,
        folder_id=parsed_folder_id,
        folder_filter_unfiled=folder_filter_unfiled,
    )

    owner_name_cache: dict[str, str | None] = {}
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
        owner_name = await _resolve_owner_name(user_repo, t.created_by, owner_name_cache)

        items.append(TemplateResponse(
            id=str(t.id),
            name=t.name,
            description=t.description,
            current_version=t.current_version,
            variables=current_vars,
            versions=[
                _version_to_response(v)
                for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
            ],
            created_at=t.created_at,
            updated_at=t.updated_at,
            access_type=access_type,
            is_owner=is_owner,
            owner_name=owner_name,
            folder_id=str(t.folder_id) if getattr(t, "folder_id", None) else None,
        ))

    return TemplateListResponse(items=items, total=total, page=page, size=size)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    user_repo: UserRepository = Depends(get_user_repository),
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
    access_type = "owned" if is_owner else ("admin" if can_view_all_templates(current_user.role) else "shared")

    shared_by_email: str | None = None
    if access_type == "shared":
        share = await service.repository.get_share_for_user(
            template_id, current_user.user_id
        )
        if share is not None:
            sharer = await user_repo.get_by_id(share.shared_by)
            if sharer is not None:
                shared_by_email = sharer.email

    owner_name = await _resolve_owner_name(user_repo, t.created_by, {})

    return TemplateResponse(
        id=str(t.id),
        name=t.name,
        description=t.description,
        current_version=t.current_version,
        variables=current_vars,
        versions=[
            _version_to_response(v)
            for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
        ],
        created_at=t.created_at,
        updated_at=t.updated_at,
        access_type=access_type,
        is_owner=is_owner,
        shared_by_email=shared_by_email,
        owner_name=owner_name,
        folder_id=str(t.folder_id) if getattr(t, "folder_id", None) else None,
    )


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    body: TemplateUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Rename, update the description, and/or re-file a template.

    Name/description follow the owner-or-admin rule. Folder assignment
    (folder_id) is strictly owner-only — no admin bypass — since folders
    are personal organization.
    """
    folder_id_provided = "folder_id" in body.model_fields_set
    parsed_folder_id: UUID | None = None
    if folder_id_provided and body.folder_id is not None:
        parsed_folder_id = UUID(body.folder_id)

    try:
        t = await service.update_template(
            template_id,
            user_id=current_user.user_id,
            role=current_user.role,
            name=body.name,
            description=body.description,
            description_provided="description" in body.model_fields_set,
            folder_id=parsed_folder_id,
            folder_id_provided=folder_id_provided,
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
    except TemplateFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carpeta no encontrada",
        )
    except DomainError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    current_vars: list[str] = []
    if t.versions:
        current_version = next(
            (v for v in t.versions if v.version == t.current_version), None
        )
        if current_version:
            current_vars = current_version.variables

    is_owner = str(getattr(t, "created_by", "")) == str(current_user.user_id)
    access_type = "owned" if is_owner else ("admin" if can_view_all_templates(current_user.role) else "shared")
    owner_name = await _resolve_owner_name(user_repo, t.created_by, {})

    return TemplateResponse(
        id=str(t.id),
        name=t.name,
        description=t.description,
        current_version=t.current_version,
        variables=current_vars,
        versions=[
            _version_to_response(v)
            for v in sorted(t.versions, key=lambda x: x.version, reverse=True)
        ],
        created_at=t.created_at,
        updated_at=t.updated_at,
        access_type=access_type,
        is_owner=is_owner,
        owner_name=owner_name,
        folder_id=str(t.folder_id) if getattr(t, "folder_id", None) else None,
    )


@router.get(
    "/{template_id}/versions/{version_id}/structure",
    response_model=TemplateStructureResponse,
)
async def get_version_structure(
    template_id: UUID,
    version_id: UUID,
    file_id: UUID | None = Query(
        None,
        description="Related file to extract the structure from instead of "
        "the primary docx. Must belong to the version.",
    ),
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """
    Return the full document structure (headers / body / footers) for a
    specific template version. Powers the generation preview UI: the user
    sees the entire document with placeholders inline instead of just the
    paragraphs that contain a given variable.

    With `?file_id=` the structure of that RELATED file is returned instead
    of the primary docx.
    """
    try:
        structure = await service.get_version_structure(
            template_id,
            version_id,
            user_id=current_user.user_id,
            role=current_user.role,
            file_id=file_id,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except TemplateVersionFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo relacionado no encontrado",
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )

    return TemplateStructureResponse(**structure)


@router.get("/{template_id}/versions/{version_id}/download")
async def download_template_version(
    template_id: UUID,
    version_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Download the stored .docx of a specific template version.

    Accessible to any user with template access (owner, shared user, or
    admin) — same gate as the structure endpoint.
    """
    try:
        file_bytes, filename = await service.download_template_version(
            template_id,
            version_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )

    # Template names can contain accents/enie — send an ASCII fallback in
    # `filename` plus the exact UTF-8 name in RFC 5987 `filename*`.
    from urllib.parse import quote

    ascii_fallback = (
        unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
        or "template.docx"
    )
    content_disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
    )


# ---------------------------------------------------------------------------
# Related files per template version — N extra .docx sharing the version's
# variable set. Managed only on the CURRENT version (owner/admin); readable
# by anyone with template access.
# ---------------------------------------------------------------------------


@router.post(
    "/{template_id}/versions/{version_id}/files",
    response_model=TemplateVersionFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_version_file(
    template_id: UUID,
    version_id: UUID,
    file: UploadFile = File(...),
    label: str = Form(..., max_length=120),
    current_user: CurrentUser = Depends(require_template_manager),
    service: TemplateService = Depends(get_template_service),
):
    """Attach a related .docx to the template's CURRENT version.

    Same gate as uploading a new version (owner or admin). The version's
    variables become the union of the current set and this file's
    extraction. 409 on duplicate label or non-current version.
    """
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    if not label.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La etiqueta no puede estar vacía",
        )

    # Validate template before upload — same pipeline as /upload
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
        created = await service.attach_version_file(
            template_id,
            version_id,
            label=label,
            file_bytes=file_bytes,
            file_size=len(file_bytes),
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    except InvalidTemplateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return _file_to_response(created)


@router.post(
    "/{template_id}/versions/{version_id}/files/from-example",
    response_model=TemplateVersionFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def attach_version_file_from_example(
    template_id: UUID,
    version_id: UUID,
    file: UploadFile = File(...),
    label: str = Form(..., max_length=120),
    mappings: str = Form(...),
    current_user: CurrentUser = Depends(require_template_manager),
    service: TemplateService = Depends(get_template_service),
):
    """Attach a related file built from a FILLED example .docx.

    `mappings` is a JSON string array of {"text", "variable"} items — same
    schema as POST /templates/from-example. The backend replaces every
    literal occurrence with {{ placeholders }} without altering Word
    formatting, then runs the standard attach pipeline on the rewritten
    bytes. Same gate as the plain attach (owner or admin); error contract is
    the union of both flows: 422 mapping variants, 409 duplicate label /
    non-current version, 400 bad docx, 403/404.
    """
    _validate_docx_upload(file)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío",
        )

    if not label.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La etiqueta no puede estar vacía",
        )

    # Parse + validate the mappings JSON form field — exact mirror of
    # /templates/from-example.
    import json

    from pydantic import ValidationError

    try:
        raw_mappings = json.loads(mappings)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El campo 'mappings' debe ser un arreglo JSON válido de objetos {text, variable}",
        )
    try:
        payload = VariableMappingsPayload(mappings=raw_mappings)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Mappings inválidos",
                "errors": [
                    f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                    for err in e.errors()
                ],
            },
        )

    try:
        created = await service.attach_version_file_from_example(
            template_id,
            version_id,
            label=label,
            file_bytes=file_bytes,
            mappings=[m.model_dump() for m in payload.mappings],
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except MappingTextNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(e),
                "missing_texts": e.missing_texts,
            },
        )
    except InvalidVariableMappingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    except InvalidTemplateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return _file_to_response(created)


@router.delete(
    "/{template_id}/versions/{version_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_version_file(
    template_id: UUID,
    version_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(require_template_manager),
    service: TemplateService = Depends(get_template_service),
):
    """Detach a related file from the template's CURRENT version (owner or
    admin). The version's variables union is recomputed from the primary's
    re-extraction plus the remaining files."""
    try:
        await service.detach_version_file(
            template_id,
            version_id,
            file_id,
            user_id=str(current_user.user_id),
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo relacionado no encontrado",
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )
    except TemplateNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    except InvalidTemplateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/{template_id}/versions/{version_id}/files/{file_id}/download")
async def download_version_file(
    template_id: UUID,
    version_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Download the stored .docx of a related file.

    Accessible to any user with template access (owner, shared user, or
    admin) — same gate as the primary version download.
    """
    try:
        file_bytes, filename = await service.download_version_file(
            template_id,
            version_id,
            file_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateVersionFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo relacionado no encontrado",
        )
    except TemplateVersionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template version not found",
        )

    # Labels/names can contain accents/enie — send an ASCII fallback in
    # `filename` plus the exact UTF-8 name in RFC 5987 `filename*`.
    from urllib.parse import quote

    ascii_fallback = (
        unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
        or "template.docx"
    )
    content_disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disposition},
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
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Share a template with another user by email (owner/admin only)."""
    # Resolve email → user_id within the same tenant
    target_user = await user_repo.get_by_email(body.email.strip().lower())

    if target_user is None or str(target_user.tenant_id) != str(current_user.tenant_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un usuario con ese correo",
        )

    try:
        share = await service.share_template(
            template_id=template_id,
            user_id=target_user.id,
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
        user_email=target_user.email,
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


@router.patch(
    "/{template_id}/versions/{version_id}/variables-meta",
    response_model=TemplateVersionResponse,
)
async def update_variable_types(
    template_id: UUID,
    version_id: UUID,
    body: UpdateVariableTypesRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
):
    """Update the type/options for variables in a template version. Owner-only."""
    try:
        updated_version = await service.update_variable_types(
            template_id=template_id,
            version_id=version_id,
            overrides=body.overrides,
            current_user_id=current_user.user_id,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template or version not found")
    except ComputedVariableValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return _version_to_response(updated_version)


@router.get("/{template_id}/shares", response_model=list[TemplateShareResponse])
async def list_template_shares(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    user_repo: UserRepository = Depends(get_user_repository),
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

    # Enrich shares with user emails for display
    result = []
    for s in shares:
        user = await user_repo.get_by_id(s.user_id)
        result.append(
            TemplateShareResponse(
                id=str(s.id),
                template_id=str(s.template_id),
                user_id=str(s.user_id),
                user_email=user.email if user is not None else None,
                tenant_id=str(s.tenant_id),
                shared_by=str(s.shared_by),
                shared_at=s.shared_at,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Template presets — recurring-client stored values
#
# Permission for ALL preset operations: template ACCESS (owner,
# shared-with-user, or admin) — the same rule as GET /templates/{id}.
# Presets are shared by everyone with access to the template (explicit
# product decision — both creators and document generators manage them).
# ---------------------------------------------------------------------------


@router.get("/{template_id}/presets", response_model=PresetListResponse)
async def list_presets(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplatePresetService = Depends(get_template_preset_service),
):
    """List a template's presets, ordered by name."""
    try:
        presets = await service.list_presets(
            template_id, user_id=current_user.user_id, role=current_user.role
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return PresetListResponse(
        presets=[
            PresetResponse(
                id=str(p.id),
                name=p.name,
                values=p.values,
                created_by=str(p.created_by),
                created_at=p.created_at,
            )
            for p in presets
        ]
    )


@router.post(
    "/{template_id}/presets", response_model=PresetResponse, status_code=status.HTTP_201_CREATED
)
async def create_preset(
    template_id: UUID,
    body: PresetCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplatePresetService = Depends(get_template_preset_service),
):
    """Create a preset for a template. Keys in `values` are NOT validated
    against the version's variables — versions evolve; the client
    intersects at load time."""
    try:
        preset = await service.create_preset(
            template_id=template_id,
            user_id=current_user.user_id,
            role=current_user.role,
            tenant_id=current_user.tenant_id,
            name=body.name,
            values=body.values,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return PresetResponse(
        id=str(preset.id),
        name=preset.name,
        values=preset.values,
        created_by=str(preset.created_by),
        created_at=preset.created_at,
    )


@router.patch("/{template_id}/presets/{preset_id}", response_model=PresetResponse)
async def update_preset(
    template_id: UUID,
    preset_id: UUID,
    body: PresetUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplatePresetService = Depends(get_template_preset_service),
):
    """Rename a preset and/or replace its values. 404 if the preset doesn't
    exist OR belongs to a different template — this never reveals the
    existence of a preset under a foreign template_id."""
    try:
        preset = await service.update_preset(
            template_id=template_id,
            preset_id=preset_id,
            user_id=current_user.user_id,
            role=current_user.role,
            name=body.name,
            name_provided="name" in body.model_fields_set,
            values=body.values,
            values_provided="values" in body.model_fields_set,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    except TemplatePresetNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset no encontrado")
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return PresetResponse(
        id=str(preset.id),
        name=preset.name,
        values=preset.values,
        created_by=str(preset.created_by),
        created_at=preset.created_at,
    )


@router.delete("/{template_id}/presets/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    template_id: UUID,
    preset_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplatePresetService = Depends(get_template_preset_service),
):
    """Delete a preset. 404 if it doesn't exist OR belongs to a different
    template — non-leaking, same rule as update_preset."""
    try:
        await service.delete_preset(
            template_id=template_id,
            preset_id=preset_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except TemplateAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except TemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    except TemplatePresetNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preset no encontrado")
