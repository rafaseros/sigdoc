from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.services import get_template_folder_service
from app.application.services.template_folder_service import TemplateFolderService
from app.domain.exceptions import DomainError, TemplateFolderNotFoundError
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.folder import (
    FolderCreateRequest,
    FolderListResponse,
    FolderResponse,
    FolderUpdateRequest,
)

router = APIRouter()


@router.get("", response_model=FolderListResponse)
async def list_folders(
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateFolderService = Depends(get_template_folder_service),
):
    """List the caller's own personal template folders, ordered by name."""
    folders = await service.list_folders(current_user.user_id)
    return FolderListResponse(
        folders=[
            FolderResponse(
                id=str(f.id),
                name=f.name,
                template_count=getattr(f, "template_count", 0),
            )
            for f in folders
        ]
    )


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateFolderService = Depends(get_template_folder_service),
):
    """Create a personal template folder owned by the caller."""
    try:
        folder = await service.create_folder(
            tenant_id=current_user.tenant_id,
            owner_id=current_user.user_id,
            name=body.name,
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return FolderResponse(id=str(folder.id), name=folder.name, template_count=0)


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: UUID,
    body: FolderUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateFolderService = Depends(get_template_folder_service),
):
    """Rename a personal template folder. 404 if it doesn't exist OR isn't
    owned by the caller — this never reveals the existence of another
    user's folder."""
    try:
        folder = await service.rename_folder(
            folder_id, owner_id=current_user.user_id, name=body.name
        )
    except TemplateFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Carpeta no encontrada"
        )
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return FolderResponse(
        id=str(folder.id),
        name=folder.name,
        template_count=getattr(folder, "template_count", 0),
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateFolderService = Depends(get_template_folder_service),
):
    """Delete a personal template folder. Templates filed in it are
    unfiled (folder_id set to NULL) at the DB level — they are never
    deleted. 404 if the folder doesn't exist OR isn't owned by the caller."""
    try:
        await service.delete_folder(folder_id, owner_id=current_user.user_id)
    except TemplateFolderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Carpeta no encontrada"
        )
