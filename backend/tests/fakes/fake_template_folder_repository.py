from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import TemplateFolder
from app.domain.exceptions import FolderNameCollisionError
from app.domain.ports.template_folder_repository import TemplateFolderRepository


class FakeTemplateFolderRepository(TemplateFolderRepository):
    """Dict-backed in-memory implementation of TemplateFolderRepository for testing.

    Optionally linked to a FakeTemplateRepository so that `delete()` can
    emulate the real DB's `ON DELETE SET NULL` FK behavior on
    `templates.folder_id`. The real SQLAlchemy repository never needs to do
    this itself — Postgres handles it via the FK constraint — but the fakes
    are separate in-memory stores with no referential integrity, so the
    emulation has to happen explicitly here.
    """

    def __init__(self, template_repo=None) -> None:
        self._folders: dict[UUID, TemplateFolder] = {}
        self._template_repo = template_repo

    async def create(self, folder: TemplateFolder) -> TemplateFolder:
        for other in self._folders.values():
            if (
                other.tenant_id == folder.tenant_id
                and other.owner_id == folder.owner_id
                and other.name == folder.name
            ):
                raise FolderNameCollisionError(folder.name)

        now = datetime.now(timezone.utc)
        if folder.created_at is None:
            folder.created_at = now
        if folder.updated_at is None:
            folder.updated_at = now
        self._folders[folder.id] = folder
        return folder

    async def get_by_id(self, folder_id: UUID) -> TemplateFolder | None:
        return self._folders.get(folder_id)

    async def list_by_owner(self, owner_id: UUID) -> list[TemplateFolder]:
        items = [f for f in self._folders.values() if f.owner_id == owner_id]
        items.sort(key=lambda f: f.name)
        for f in items:
            f.template_count = self._count_templates_in_folder(f.id)
        return items

    async def update(self, folder_id: UUID, *, name: str) -> TemplateFolder:
        folder = self._folders.get(folder_id)
        if folder is None:
            raise KeyError(f"Folder {folder_id} not found")

        for other in self._folders.values():
            if (
                other.id != folder_id
                and other.tenant_id == folder.tenant_id
                and other.owner_id == folder.owner_id
                and other.name == name
            ):
                raise FolderNameCollisionError(name)

        folder.name = name
        folder.updated_at = datetime.now(timezone.utc)
        return folder

    async def delete(self, folder_id: UUID) -> None:
        self._folders.pop(folder_id, None)
        if self._template_repo is not None:
            for template in self._template_repo._templates.values():
                if getattr(template, "folder_id", None) == folder_id:
                    template.folder_id = None

    def _count_templates_in_folder(self, folder_id: UUID) -> int:
        """Mirrors the real repository's defense-in-depth correlation: only
        count templates whose `created_by` matches the folder's `owner_id`
        — a template can never legitimately count towards a folder it has
        no ownership relationship with."""
        if self._template_repo is None:
            return 0
        folder = self._folders.get(folder_id)
        if folder is None:
            return 0
        return sum(
            1
            for t in self._template_repo._templates.values()
            if getattr(t, "folder_id", None) == folder_id
            and getattr(t, "created_by", None) == folder.owner_id
        )
