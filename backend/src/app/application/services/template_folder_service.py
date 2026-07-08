from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import TemplateFolder
from app.domain.exceptions import DomainError, FolderNameCollisionError, TemplateFolderNotFoundError
from app.domain.ports.template_folder_repository import TemplateFolderRepository

if TYPE_CHECKING:
    from app.application.services.audit_service import AuditService


class TemplateFolderService:
    """Personal, flat (non-nested) folders for organizing the owner's own
    templates. Folders are strictly owner-scoped — there is no admin bypass
    and no tenant-wide visibility, matching the strict-owner pattern already
    used for template shares and variables-meta."""

    def __init__(
        self,
        repository: TemplateFolderRepository,
        audit_service: AuditService | None = None,
        ip_address: str | None = None,
    ):
        self._repository = repository
        self._audit_service = audit_service
        self._ip_address = ip_address

    async def list_folders(self, owner_id: UUID) -> list[TemplateFolder]:
        """Return the caller's own folders, ordered by name, each carrying a
        transient `template_count` attribute."""
        return await self._repository.list_by_owner(owner_id)

    async def create_folder(
        self, *, tenant_id: UUID, owner_id: UUID, name: str
    ) -> TemplateFolder:
        folder = TemplateFolder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=name,
        )
        try:
            created = await self._repository.create(folder)
        except FolderNameCollisionError:
            raise DomainError(
                f"Ya existe una carpeta con el nombre '{name}'. Use un nombre diferente."
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            self._audit_service.log(
                actor_id=owner_id,
                tenant_id=tenant_id,
                action=AuditAction.FOLDER_CREATE,
                resource_type="template_folder",
                resource_id=created.id,
                details={"name": created.name},
                ip_address=self._ip_address,
            )

        return created

    async def rename_folder(
        self, folder_id: UUID, *, owner_id: UUID, name: str
    ) -> TemplateFolder:
        folder = await self._get_owned_folder(folder_id, owner_id)
        old_name = folder.name

        try:
            updated = await self._repository.update(folder_id, name=name)
        except FolderNameCollisionError:
            raise DomainError(
                f"Ya existe una carpeta con el nombre '{name}'. Use un nombre diferente."
            )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            self._audit_service.log(
                actor_id=owner_id,
                tenant_id=folder.tenant_id,
                action=AuditAction.FOLDER_UPDATE,
                resource_type="template_folder",
                resource_id=folder_id,
                details={"old_name": old_name, "new_name": updated.name},
                ip_address=self._ip_address,
            )

        return updated

    async def delete_folder(self, folder_id: UUID, *, owner_id: UUID) -> None:
        folder = await self._get_owned_folder(folder_id, owner_id)

        await self._repository.delete(folder_id)

        if self._audit_service is not None:
            from app.domain.entities import AuditAction

            self._audit_service.log(
                actor_id=owner_id,
                tenant_id=folder.tenant_id,
                action=AuditAction.FOLDER_DELETE,
                resource_type="template_folder",
                resource_id=folder_id,
                details={"name": folder.name},
                ip_address=self._ip_address,
            )

    async def _get_owned_folder(self, folder_id: UUID, owner_id: UUID) -> TemplateFolder:
        """Return the folder if it exists AND belongs to owner_id — otherwise
        raise TemplateFolderNotFoundError, never distinguishing between "does
        not exist" and "belongs to someone else" so the 404 never leaks the
        existence of another user's folder."""
        folder = await self._repository.get_by_id(folder_id)
        if folder is None or folder.owner_id != owner_id:
            raise TemplateFolderNotFoundError(f"Folder {folder_id} not found")
        return folder
