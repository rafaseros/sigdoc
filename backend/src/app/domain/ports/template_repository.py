from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Template, TemplateVersion


class TemplateRepository(ABC):
    @abstractmethod
    async def create(self, template: Template) -> Template:
        ...

    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Template | None:
        ...

    @abstractmethod
    async def list_paginated(
        self, page: int = 1, size: int = 20, search: str | None = None
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
        file_size: int,
    ) -> Template:
        """Create a template and its first version atomically."""
        ...
