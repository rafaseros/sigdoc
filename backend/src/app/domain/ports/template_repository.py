from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Template, TemplateShare, TemplateVersion


class TemplateRepository(ABC):
    @abstractmethod
    async def create(self, template: Template) -> Template:
        ...

    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Template | None:
        ...

    @abstractmethod
    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[Template], int]:
        ...

    @abstractmethod
    async def delete(self, template_id: UUID) -> None:
        ...

    @abstractmethod
    async def create_version(self, version: TemplateVersion) -> TemplateVersion:
        ...

    @abstractmethod
    async def get_version(self, template_id: UUID, version: int) -> TemplateVersion | None:
        ...

    @abstractmethod
    async def get_version_by_id(self, version_id: UUID) -> TemplateVersion | None:
        ...

    @abstractmethod
    async def create_template_with_version(
        self,
        *,
        template_id: UUID,
        version_id: UUID,
        name: str,
        description: str | None,
        tenant_id: UUID,
        created_by: UUID,
        version: int,
        minio_path: str,
        variables: list[str],
        variables_meta: list[dict] | None = None,
        file_size: int,
    ) -> Template:
        """Create a template and its first version atomically."""
        ...

    @abstractmethod
    async def list_accessible(
        self,
        user_id: UUID,
        role: str,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Template], int]:
        """Return templates where user is owner OR has a share record.
        Admin role sees all templates in the tenant."""
        ...

    @abstractmethod
    async def add_share(
        self,
        template_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        shared_by: UUID,
    ) -> TemplateShare:
        """Create a share record. Idempotent — ON CONFLICT DO NOTHING."""
        ...

    @abstractmethod
    async def remove_share(self, template_id: UUID, user_id: UUID) -> None:
        """Delete the share record for (template_id, user_id)."""
        ...

    @abstractmethod
    async def has_access(self, template_id: UUID, user_id: UUID, role: str) -> bool:
        """Return True if user owns the template, has a share, or is admin."""
        ...

    @abstractmethod
    async def list_shares(self, template_id: UUID) -> list[TemplateShare]:
        """Return all share records for a given template."""
        ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Return the total number of templates owned by the given tenant."""
        ...

    @abstractmethod
    async def count_shares(self, template_id: UUID) -> int:
        """Return the number of active share records for the given template."""
        ...
