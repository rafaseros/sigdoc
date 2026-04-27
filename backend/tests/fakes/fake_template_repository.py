import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import Template, TemplateShare, TemplateVersion
from app.domain.ports.template_repository import TemplateRepository


class FakeTemplateRepository(TemplateRepository):
    """Dict-backed in-memory implementation of TemplateRepository for testing."""

    def __init__(self) -> None:
        self._templates: dict[UUID, Template] = {}
        self._versions: dict[UUID, TemplateVersion] = {}
        # _shares: {(template_id, user_id): TemplateShare}
        self._shares: dict[tuple[UUID, UUID], TemplateShare] = {}

    async def create(self, template: Template) -> Template:
        now = datetime.now(timezone.utc)
        if template.created_at is None:
            template.created_at = now
        if template.updated_at is None:
            template.updated_at = now
        self._templates[template.id] = template
        return template

    async def get_by_id(self, template_id: UUID) -> Template | None:
        return self._templates.get(template_id)

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[Template], int]:
        items = list(self._templates.values())

        if search:
            search_lower = search.lower()
            items = [t for t in items if search_lower in t.name.lower()]

        if created_by is not None:
            items = [t for t in items if t.created_by == created_by]

        total = len(items)
        offset = (page - 1) * size
        page_items = items[offset : offset + size]

        return page_items, total

    async def delete(self, template_id: UUID) -> None:
        self._templates.pop(template_id, None)
        # Remove all versions that belong to this template
        to_remove = [
            vid for vid, v in self._versions.items() if v.template_id == template_id
        ]
        for vid in to_remove:
            del self._versions[vid]

    async def create_version(self, version: TemplateVersion) -> TemplateVersion:
        # Mirror create_template_with_version: populate created_at if missing
        if version.created_at is None:
            version.created_at = datetime.now(timezone.utc)
        self._versions[version.id] = version
        # Update parent template's current_version if template exists
        template = self._templates.get(version.template_id)
        if template is not None:
            template.versions.append(version)
            if version.version > template.current_version:
                template.current_version = version.version
        return version

    async def get_version(
        self, template_id: UUID, version: int
    ) -> TemplateVersion | None:
        for v in self._versions.values():
            if v.template_id == template_id and v.version == version:
                return v
        return None

    async def get_version_by_id(self, version_id: UUID) -> TemplateVersion | None:
        return self._versions.get(version_id)

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
        template_version = TemplateVersion(
            id=version_id,
            tenant_id=tenant_id,
            template_id=template_id,
            version=version,
            minio_path=minio_path,
            variables=variables,
            variables_meta=variables_meta,
            file_size=file_size,
        )
        self._versions[version_id] = template_version

        now = datetime.now(timezone.utc)
        if template_version.created_at is None:
            template_version.created_at = now

        template = Template(
            id=template_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            current_version=version,
            created_by=created_by,
            versions=[template_version],
            created_at=now,
            updated_at=now,
        )
        self._templates[template_id] = template
        return template

    async def list_accessible(
        self,
        user_id: UUID,
        role: str,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> tuple[list[Template], int]:
        """Return templates where user is owner OR has a share. Admins see all."""
        items = list(self._templates.values())

        if role != "admin":
            # Shared template_ids for this user
            shared_ids = {
                share.template_id
                for share in self._shares.values()
                if share.user_id == user_id
            }
            items = [t for t in items if t.created_by == user_id or t.id in shared_ids]

        if search:
            search_lower = search.lower()
            items = [t for t in items if search_lower in t.name.lower()]

        # Attach transient access_type
        for t in items:
            key = (t.id, user_id)
            if role == "admin" and t.created_by != user_id:
                t.access_type = "shared"
            elif key in self._shares and t.created_by != user_id:
                t.access_type = "shared"
            else:
                t.access_type = "owned"

        total = len(items)
        offset = (page - 1) * size
        return items[offset: offset + size], total

    async def add_share(
        self,
        template_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        shared_by: UUID,
    ) -> TemplateShare:
        """Create a share record. Idempotent — do not error on duplicate."""
        key = (template_id, user_id)
        if key in self._shares:
            # Idempotent: return the existing share
            return self._shares[key]
        share = TemplateShare(
            id=uuid.uuid4(),
            template_id=template_id,
            user_id=user_id,
            tenant_id=tenant_id,
            shared_by=shared_by,
            shared_at=datetime.now(timezone.utc),
        )
        self._shares[key] = share
        return share

    async def remove_share(self, template_id: UUID, user_id: UUID) -> None:
        """Delete the share record for (template_id, user_id)."""
        self._shares.pop((template_id, user_id), None)

    async def has_access(self, template_id: UUID, user_id: UUID, role: str) -> bool:
        """Return True if user owns the template, has a share, or is admin."""
        if role == "admin":
            return True
        template = self._templates.get(template_id)
        if template is None:
            return False
        if template.created_by == user_id:
            return True
        return (template_id, user_id) in self._shares

    async def list_shares(self, template_id: UUID) -> list[TemplateShare]:
        """Return all share records for a given template."""
        return [
            share
            for (tid, _), share in self._shares.items()
            if tid == template_id
        ]

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Return total number of templates owned by the given tenant."""
        return sum(1 for t in self._templates.values() if t.tenant_id == tenant_id)

    async def count_shares(self, template_id: UUID) -> int:
        """Return number of share records for the given template."""
        return sum(1 for (tid, _) in self._shares if tid == template_id)

    async def get_owner_id(self, template_id: UUID) -> UUID | None:
        """Return the owner (created_by) UUID for the given template, or None."""
        template = self._templates.get(template_id)
        if template is None:
            return None
        return template.created_by

    async def get_share_for_user(
        self, template_id: UUID, user_id: UUID
    ) -> TemplateShare | None:
        """Return the share row for (template_id, user_id), or None if absent."""
        return self._shares.get((template_id, user_id))
