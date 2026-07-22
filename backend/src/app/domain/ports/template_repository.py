from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Template, TemplateShare, TemplateVersion, TemplateVersionFile


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
    async def get_version_by_id_for_update(
        self, version_id: UUID
    ) -> TemplateVersion | None:
        """Fetch a template version row with a row-level write lock
        (SELECT ... FOR UPDATE). Concurrent callers requesting the lock on
        the SAME version block until the holder's transaction commits, then
        observe its committed state. Used to serialize the variables
        read-modify-write in attach_version_file so overlapping attaches to
        the same version never drop each other's variables. Returns None when
        the version does not exist."""
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
        folder_id: UUID | None = None,
        folder_filter_unfiled: bool = False,
    ) -> tuple[list[Template], int]:
        """Return templates where user is owner OR has a share record.
        Admin role sees all templates in the tenant.

        `folder_filter_unfiled=True` restricts results to templates with no
        folder (folder_id IS NULL); `folder_id` (when `folder_filter_unfiled`
        is False) restricts results to that specific folder. The folder
        filter MUST be intersected with the owner/shared visibility rule for
        non-admin callers — never applied as an independent query — or
        another owner's shared templates could leak through a folder filter.
        """
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

    @abstractmethod
    async def get_owner_id(self, template_id: UUID) -> UUID | None:
        """Return the created_by (owner) UUID for the given template, or None if not found."""
        ...

    @abstractmethod
    async def get_share_for_user(
        self, template_id: UUID, user_id: UUID
    ) -> TemplateShare | None:
        """Return the share row for (template_id, user_id), or None if absent."""
        ...

    @abstractmethod
    async def update_variables_meta(
        self, version_id: UUID, variables_meta: list[dict]
    ) -> TemplateVersion:
        """Replace variables_meta for the given version and return the updated entity."""
        ...

    @abstractmethod
    async def add_version_file(
        self, file: TemplateVersionFile
    ) -> TemplateVersionFile:
        """Persist a related file row for a template version and return it."""
        ...

    @abstractmethod
    async def get_version_file(
        self, version_id: UUID, file_id: UUID
    ) -> TemplateVersionFile | None:
        """Return the related file for (version_id, file_id), or None when it
        does not exist OR belongs to a different version (non-leaking)."""
        ...

    @abstractmethod
    async def delete_version_file(self, version_id: UUID, file_id: UUID) -> None:
        """Delete the related file row for (version_id, file_id)."""
        ...

    @abstractmethod
    async def update_version_variables(
        self, version_id: UUID, variables: list[str], variables_meta: list[dict]
    ) -> TemplateVersion:
        """Replace BOTH variables and variables_meta for the given version
        (used to store the primary+related-files union) and return the
        updated entity."""
        ...

    @abstractmethod
    async def count_by_owner(self, user_id: UUID) -> int:
        """Return how many templates the given user owns. Used to decide
        whether deactivating that user requires a reassign target."""
        ...

    @abstractmethod
    async def reassign_owner(
        self, from_user_id: UUID, to_user_id: UUID
    ) -> int:
        """Bulk reassign every template owned by `from_user_id` to
        `to_user_id`. Returns the number of templates updated. Caller is
        responsible for validating that both users belong to the same
        tenant before invoking this."""
        ...

    @abstractmethod
    async def update(
        self,
        template_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        description_provided: bool = False,
        folder_id: UUID | None = None,
        folder_id_provided: bool = False,
    ) -> Template:
        """Update the given fields on a template and return the updated entity.

        `name` is applied when not None (name can never be cleared). `description`
        is applied whenever `description_provided` is True — including clearing it
        to None — which lets callers distinguish an explicit null from an omitted
        field. `folder_id` follows the same explicit-null pattern via
        `folder_id_provided`: setting it to None while `folder_id_provided=True`
        unfiles the template. Raises TemplateNameCollisionError on a
        (tenant_id, name) collision — the caller is responsible for catching it
        and mapping it to a domain error. Callers are responsible for validating
        that the target folder exists and belongs to the caller BEFORE invoking
        this method — this method does not re-validate folder ownership."""
        ...
