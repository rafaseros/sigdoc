from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import TemplateShare, TemplateVersion
from app.domain.exceptions import (
    DomainError,
    InvalidTemplateError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
    TemplateSharingError,
    TemplateVersionNotFoundError,
)
from app.domain.ports.storage_service import StorageService
from app.domain.ports.template_engine import TemplateEngine
from app.domain.ports.template_repository import TemplateRepository
from app.domain.services.permissions import can_view_all_templates

if TYPE_CHECKING:
    from app.application.services.audit_service import AuditService
    from app.application.services.quota_service import QuotaService


class TemplateService:
    TEMPLATES_BUCKET = "templates"

    def __init__(
        self,
        repository: TemplateRepository,
        storage: StorageService,
        engine: TemplateEngine,
        audit_service: AuditService | None = None,
        ip_address: str | None = None,
        quota_service: QuotaService | None = None,
        tier_id: UUID | None = None,
    ):
        self._repository = repository
        self._storage = storage
        self._engine = engine
        self._audit_service = audit_service
        self._ip_address = ip_address
        self._quota_service = quota_service
        self._tier_id = tier_id

    @property
    def repository(self) -> TemplateRepository:
        """Expose the underlying repository for endpoint-level lookups."""
        return self._repository

    async def get_version_structure(
        self,
        template_id: UUID,
        version_id: UUID,
        *,
        user_id: str,
        role: str | None,
    ) -> dict:
        """
        Return the document structure (headers / body / footers) for a specific
        template version, used by the generation preview UI.

        Raises:
            TemplateVersionNotFoundError: version doesn't exist OR belongs to
                a different template than the URL path indicates.
            TemplateAccessDeniedError: user can't read this template.
        """
        version = await self._repository.get_version_by_id(version_id)
        if version is None or version.template_id != template_id:
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        # CurrentUser.user_id can be a UUID instance (test fixture) or a string
        # (real auth flow); normalise so has_access always sees a UUID.
        user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        has_access = await self._repository.has_access(
            version.template_id, user_uuid, role
        )
        if not has_access:
            raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )
        return await self._engine.extract_structure(template_bytes)

    async def upload_template(
        self,
        name: str,
        file_bytes: bytes,
        file_size: int,
        tenant_id: str,
        created_by: str,
        description: str | None = None,
    ) -> dict:
        """
        Upload a new template:
        1. Validate file is a valid .docx
        2. Extract variables from template
        3. Store file in MinIO
        4. Create template + version in DB
        """
        # 0. Quota check (optional — skipped when quota_service is None)
        if self._quota_service is not None and self._tier_id is not None:
            await self._quota_service.check_template_limit(
                tenant_id=uuid.UUID(tenant_id),
                tier_id=self._tier_id,
            )

        # 1. Extract variables (also validates it's a valid docx with Jinja2 tags)
        try:
            variables_meta = await self._engine.extract_variables(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")

        # Extract plain variable names for backwards compatibility
        variables = [v["name"] for v in variables_meta]

        # 2. Generate IDs
        template_id = uuid.uuid4()
        version_id = uuid.uuid4()
        version = 1

        # 3. Store in MinIO
        minio_path = f"{tenant_id}/{template_id}/v{version}/template.docx"
        await self._storage.upload_file(
            bucket=self.TEMPLATES_BUCKET,
            path=minio_path,
            data=file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # 4. Create DB records atomically
        from sqlalchemy.exc import IntegrityError

        try:
            template = await self._repository.create_template_with_version(
                template_id=template_id,
                version_id=version_id,
                name=name,
                description=description,
                tenant_id=uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id,
                created_by=uuid.UUID(created_by) if isinstance(created_by, str) else created_by,
                version=version,
                minio_path=minio_path,
                variables=variables,
                variables_meta=variables_meta,
                file_size=file_size,
            )
        except IntegrityError:
            raise DomainError(
                f"Ya existe una plantilla con el nombre '{name}'. Use un nombre diferente."
            )

        # Audit the upload
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            actor_uuid = uuid.UUID(created_by) if isinstance(created_by, str) else created_by
            tenant_uuid = uuid.UUID(tenant_id) if isinstance(tenant_id, str) else tenant_id
            self._audit_service.log(
                actor_id=actor_uuid,
                tenant_id=tenant_uuid,
                action=AuditAction.TEMPLATE_UPLOAD,
                resource_type="template",
                resource_id=template_id,
                ip_address=self._ip_address,
            )

        return template

    async def _check_access(
        self,
        template_id: UUID,
        user_id: UUID,
        role: str,
        require_owner: bool = False,
    ) -> None:
        """Raise TemplateAccessDeniedError if the user lacks permission.

        require_owner=True  → only owner or admin
        require_owner=False → owner, shared user, or admin
        """
        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        if can_view_all_templates(role):
            return

        is_owner = template.created_by == user_id
        if is_owner:
            return

        if require_owner:
            raise TemplateAccessDeniedError(
                "Solo el propietario o un administrador puede realizar esta acción"
            )

        # For non-owner read/generate access: check share record
        has_share = await self._repository.has_access(template_id, user_id, role)
        if not has_share:
            raise TemplateAccessDeniedError(
                "No tenés acceso a esta plantilla"
            )

    async def upload_new_version(
        self,
        template_id: str,
        file_bytes: bytes,
        file_size: int,
        tenant_id: str,
        user_id: str | None = None,
        role: str = "user",
    ) -> dict:
        """
        Upload a new version of an existing template:
        1. Get the template (verify it exists)
        2. Extract variables from new file
        3. Store file in MinIO with new version number
        4. Create new TemplateVersion record
        5. Update template.current_version
        """
        template = await self._repository.get_by_id(uuid.UUID(template_id))
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Ownership check — only owner or admin can upload new versions
        if user_id is not None:
            await self._check_access(
                uuid.UUID(template_id),
                uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
                role,
                require_owner=True,
            )

        # Extract variables (also validates it's a valid docx)
        try:
            variables_meta = await self._engine.extract_variables(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")

        # Extract plain variable names for backwards compatibility
        variables = [v["name"] for v in variables_meta]

        # New version number
        new_version = template.current_version + 1
        version_id = uuid.uuid4()

        # Store in MinIO
        minio_path = f"{tenant_id}/{template_id}/v{new_version}/template.docx"
        await self._storage.upload_file(
            bucket=self.TEMPLATES_BUCKET,
            path=minio_path,
            data=file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # Create version record (domain entity — repo handles ORM mapping)
        version_entity = TemplateVersion(
            id=version_id,
            tenant_id=uuid.UUID(tenant_id),
            template_id=uuid.UUID(template_id),
            version=new_version,
            minio_path=minio_path,
            variables=variables,
            variables_meta=variables_meta,
            file_size=file_size,
        )
        await self._repository.create_version(version_entity)

        # Update template's current_version
        template.current_version = new_version

        # Re-fetch to get updated versions list
        updated_template = await self._repository.get_by_id(uuid.UUID(template_id))

        # Audit the new version upload
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            actor_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            tenant_uuid = uuid.UUID(tenant_id)
            self._audit_service.log(
                actor_id=actor_uuid,
                tenant_id=tenant_uuid,
                action=AuditAction.TEMPLATE_VERSION,
                resource_type="template",
                resource_id=uuid.UUID(template_id),
                details={"version": new_version},
                ip_address=self._ip_address,
            )

        return {
            "template": updated_template,
            "new_version": new_version,
            "variables": variables,
        }

    async def get_template(
        self,
        template_id: uuid.UUID,
        user_id: UUID | None = None,
        role: str = "user",
    ):
        """Get template by ID with versions. Enforces access if user_id is provided."""
        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        if user_id is not None:
            await self._check_access(template_id, user_id, role, require_owner=False)

        return template

    async def list_templates(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        user_id: str | UUID | None = None,
        role: str = "user",
    ) -> tuple[list, int]:
        """List templates accessible to the requesting user (owned + shared + admin)."""
        if user_id is not None:
            uid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            return await self._repository.list_accessible(
                user_id=uid, role=role, page=page, size=size, search=search
            )
        # Fallback for callers that don't pass user_id (e.g. internal/admin bulk queries)
        return await self._repository.list_paginated(page=page, size=size, search=search)

    async def delete_template(
        self,
        template_id: uuid.UUID,
        user_id: UUID | None = None,
        role: str = "user",
    ) -> None:
        """Delete template and all its versions from DB. MinIO files remain for now."""
        from sqlalchemy.exc import IntegrityError

        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Ownership check — only owner or admin can delete
        if user_id is not None:
            await self._check_access(template_id, user_id, role, require_owner=True)

        try:
            await self._repository.delete(template_id)
        except IntegrityError:
            raise DomainError(
                "No se puede eliminar esta plantilla porque tiene documentos generados. "
                "Elimine los documentos primero."
            )

        # Audit the deletion
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=user_id,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_DELETE,
                resource_type="template",
                resource_id=template_id,
                ip_address=self._ip_address,
            )

    async def share_template(
        self,
        template_id: UUID,
        user_id: UUID,
        current_user_id: UUID,
        role: str,
        tenant_id: UUID,
    ) -> TemplateShare:
        """Share a template with another user. Only the template owner can share."""
        # Strict ownership check — admin bypass intentionally removed for share/unshare.
        template = await self._repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        if str(template.created_by) != str(current_user_id):
            raise TemplateAccessDeniedError(
                "Only the template owner can share or unshare it"
            )

        # Cross-tenant guard: the target user must belong to the same tenant.
        # We validate indirectly — the template's tenant_id must match.

        if template.tenant_id != tenant_id:
            raise TemplateSharingError(
                "No se puede compartir una plantilla con un usuario de otro tenant"
            )

        # Quota check (optional — skipped when quota_service is None)
        if self._quota_service is not None and self._tier_id is not None:
            await self._quota_service.check_share_limit(
                tenant_id=tenant_id,
                tier_id=self._tier_id,
                template_id=template_id,
            )

        share = await self._repository.add_share(
            template_id=template_id,
            user_id=user_id,
            tenant_id=tenant_id,
            shared_by=current_user_id,
        )

        # Audit the share
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=current_user_id,
                tenant_id=tenant_id,
                action=AuditAction.TEMPLATE_SHARE,
                resource_type="template",
                resource_id=template_id,
                details={"shared_with": str(user_id)},
                ip_address=self._ip_address,
            )

        return share

    async def unshare_template(
        self,
        template_id: UUID,
        user_id: UUID,
        current_user_id: UUID,
        role: str,
    ) -> None:
        """Revoke a user's access to a template. Only the template owner can unshare."""
        # Strict ownership check — admin bypass intentionally removed for share/unshare.
        template = await self._repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        if str(template.created_by) != str(current_user_id):
            raise TemplateAccessDeniedError(
                "Only the template owner can share or unshare it"
            )

        await self._repository.remove_share(template_id, user_id)

        # Audit the unshare
        if self._audit_service is not None and template is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=current_user_id,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_UNSHARE,
                resource_type="template",
                resource_id=template_id,
                details={"unshared_from": str(user_id)},
                ip_address=self._ip_address,
            )

    async def list_template_shares(
        self,
        template_id: UUID,
        current_user_id: UUID,
        role: str,
    ) -> list[TemplateShare]:
        """List all shares for a template. Accessible to owner, shared users, or admin."""
        await self._check_access(template_id, current_user_id, role, require_owner=False)
        return await self._repository.list_shares(template_id)

    async def update_variable_types(
        self,
        template_id: UUID,
        version_id: UUID,
        overrides: list,
        current_user_id: UUID,
    ) -> TemplateVersion:
        """Update type and options for variables in a template version.

        Strict owner-only: only the template creator can update variable types.
        Admin bypass is intentionally absent (matching share/unshare pattern).
        Overrides for unknown variable names are silently ignored.
        """
        template = await self._repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Strict ownership check — no admin bypass
        if str(template.created_by) != str(current_user_id):
            raise TemplateAccessDeniedError(
                "Only the template owner can update variable types"
            )

        # Find the version
        version = await self._repository.get_version_by_id(version_id)
        if version is None:
            raise TemplateNotFoundError(f"Version {version_id} not found")

        # Merge overrides into a copy of the existing variables_meta
        existing_meta = list(version.variables_meta or [])
        override_map = {o.name: o for o in overrides}

        updated_meta = []
        for entry in existing_meta:
            name = entry.get("name") if isinstance(entry, dict) else entry.name
            if name in override_map:
                override = override_map[name]
                new_entry = dict(entry) if isinstance(entry, dict) else {"name": entry.name, "contexts": entry.contexts}
                new_entry["type"] = override.type
                new_entry["options"] = override.options
                new_entry["help_text"] = override.help_text
                updated_meta.append(new_entry)
            else:
                updated_meta.append(dict(entry) if isinstance(entry, dict) else {"name": entry.name, "contexts": entry.contexts})

        updated_version = await self._repository.update_variables_meta(version_id, updated_meta)

        # Audit
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=current_user_id,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_VARIABLE_TYPES_UPDATED,
                resource_type="template_version",
                resource_id=version_id,
                details={"overrides": len(overrides)},
                ip_address=self._ip_address,
            )

        return updated_version
