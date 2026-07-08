from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import TemplateFolder


class TemplateFolderRepository(ABC):
    @abstractmethod
    async def create(self, folder: TemplateFolder) -> TemplateFolder:
        """Create a folder. Raises FolderNameCollisionError on a
        (tenant_id, owner_id, name) collision."""
        ...

    @abstractmethod
    async def get_by_id(self, folder_id: UUID) -> TemplateFolder | None:
        ...

    @abstractmethod
    async def list_by_owner(self, owner_id: UUID) -> list[TemplateFolder]:
        """Return the owner's folders, ordered by name. Each returned entity
        carries a transient `template_count` attribute — the number of
        templates currently filed in that folder — mirroring the transient
        `access_type` attribute pattern used by TemplateRepository."""
        ...

    @abstractmethod
    async def update(self, folder_id: UUID, *, name: str) -> TemplateFolder:
        """Rename a folder. Raises FolderNameCollisionError on a
        (tenant_id, owner_id, name) collision."""
        ...

    @abstractmethod
    async def delete(self, folder_id: UUID) -> None:
        """Delete a folder. Templates filed in it are unfiled (folder_id set
        to NULL) at the DB level via ON DELETE SET NULL on
        templates.folder_id — this method never touches the templates
        table directly."""
        ...
