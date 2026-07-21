from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.entities import Template, TemplateShare, TemplateVersion, TemplateVersionFile
from app.domain.exceptions import (
    ComputedVariableValidationError,
    DomainError,
    InvalidTemplateError,
    TemplateAccessDeniedError,
    TemplateFolderNotFoundError,
    TemplateNameCollisionError,
    TemplateNotFoundError,
    TemplateSharingError,
    TemplateVersionFileNotFoundError,
    TemplateVersionNotFoundError,
)
from app.domain.ports.storage_service import StorageService
from app.domain.ports.template_engine import TemplateEngine
from app.domain.ports.template_folder_repository import TemplateFolderRepository
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
        folder_repository: TemplateFolderRepository | None = None,
    ):
        self._repository = repository
        self._storage = storage
        self._engine = engine
        self._audit_service = audit_service
        self._ip_address = ip_address
        self._quota_service = quota_service
        self._tier_id = tier_id
        self._folder_repository = folder_repository

    @property
    def repository(self) -> TemplateRepository:
        """Expose the underlying repository for endpoint-level lookups."""
        return self._repository

    async def count_user_templates(self, user_id: UUID) -> int:
        """Return how many templates the given user owns. Wrapper around the
        repository — used by the user-deactivation flow to decide whether
        a reassign target is mandatory."""
        return await self._repository.count_by_owner(user_id)

    async def reassign_templates_owner(
        self, from_user_id: UUID, to_user_id: UUID
    ) -> int:
        """Bulk reassign every template owned by `from_user_id` to
        `to_user_id`. Tenant validation is the caller's responsibility —
        this method only manipulates ownership rows."""
        return await self._repository.reassign_owner(from_user_id, to_user_id)

    async def get_version_structure(
        self,
        template_id: UUID,
        version_id: UUID,
        *,
        user_id: str,
        role: str | None,
        file_id: UUID | None = None,
    ) -> dict:
        """
        Return the document structure (headers / body / footers) for a specific
        template version, used by the generation preview UI.

        When `file_id` is given, the structure of that RELATED file is
        extracted instead of the primary docx.

        Raises:
            TemplateVersionNotFoundError: version doesn't exist OR belongs to
                a different template than the URL path indicates.
            TemplateVersionFileNotFoundError: file_id doesn't exist OR belongs
                to a different version.
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

        path = version.minio_path
        if file_id is not None:
            file = await self._repository.get_version_file(version_id, file_id)
            if file is None:
                raise TemplateVersionFileNotFoundError(
                    f"Template version file {file_id} not found"
                )
            path = file.minio_path

        template_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=path,
        )
        return await self._engine.extract_structure(template_bytes)

    async def download_template_version(
        self,
        template_id: UUID,
        version_id: UUID,
        *,
        user_id: str,
        role: str | None,
    ) -> tuple[bytes, str]:
        """
        Return the stored .docx bytes of a specific template version together
        with a download filename ``{template.name}_v{version}.docx``.

        The template name is minimally sanitized for Content-Disposition
        safety (keeps letters/digits including accents, spaces, ``_`` and
        ``-`` — same rule as generate_excel_template).

        Access gate mirrors get_version_structure: any user with template
        access (owner, shared user, or admin).

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

        template = await self._repository.get_by_id(version.template_id)
        if template is None:
            # FK guarantees the parent exists; defensive, non-leaking.
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        file_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )

        safe_name = "".join(
            c for c in template.name if c.isalnum() or c in " _-"
        ).strip()
        filename = f"{safe_name or 'plantilla'}_v{version.version}.docx"

        # Audit the version download (same optional pattern as uploads)
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_DOWNLOAD,
                resource_type="template",
                resource_id=template.id,
                details={"version": version.version, "version_id": str(version_id)},
                ip_address=self._ip_address,
            )

        return file_bytes, filename

    # ------------------------------------------------------------------
    # Related files per template version (shared variable set)
    # ------------------------------------------------------------------

    async def attach_version_file(
        self,
        template_id: UUID,
        version_id: UUID,
        *,
        label: str,
        file_bytes: bytes,
        file_size: int,
        user_id: str,
        role: str = "user",
    ) -> TemplateVersionFile:
        """Attach a related .docx to the template's CURRENT version.

        The version's variables/variables_meta become the union of the
        current set and the new file's extraction: existing names keep their
        order and meta entries as-is; genuinely new names are appended with
        the engine-produced default entries (same shape upload_template
        stores).

        Gates: owner-or-admin (same as upload_new_version); the version must
        belong to the template AND be the template's current version.

        Raises:
            TemplateNotFoundError / TemplateVersionNotFoundError: 404s.
            TemplateAccessDeniedError: caller is not owner nor admin.
            DomainError: non-current version, invalid label, or duplicate
                label within the version (mapped to 409 by the endpoint).
            InvalidTemplateError: the file is not a valid docx template.
        """
        template = await self._repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        await self._check_access(template_id, user_uuid, role, require_owner=True)

        version = await self._repository.get_version_by_id(version_id)
        if version is None or version.template_id != template_id:
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        if version.version != template.current_version:
            raise DomainError(
                "Los archivos relacionados solo se pueden gestionar en la "
                "versión vigente de la plantilla"
            )

        clean_label = (label or "").strip()
        if not clean_label or len(clean_label) > 120:
            raise DomainError(
                "La etiqueta debe tener entre 1 y 120 caracteres"
            )

        existing_files = sorted(
            list(getattr(version, "files", []) or []), key=lambda f: f.position
        )
        if any(f.label == clean_label for f in existing_files):
            raise DomainError(
                f"Ya existe un archivo relacionado con la etiqueta "
                f"'{clean_label}' en esta versión. Use una etiqueta diferente."
            )

        try:
            file_meta = await self._engine.extract_variables(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")
        file_variables = [v["name"] for v in file_meta]

        file_id = uuid.uuid4()
        minio_path = (
            f"{version.tenant_id}/{template_id}/v{version.version}/files/{file_id}.docx"
        )
        await self._storage.upload_file(
            bucket=self.TEMPLATES_BUCKET,
            path=minio_path,
            data=file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        next_position = max((f.position for f in existing_files), default=-1) + 1

        # Duplicate-label race guard: two concurrent attaches with the same
        # label both pass the app-level check above; the loser hits the
        # uq_template_version_files_version_label unique constraint. Translate
        # to the SAME domain error the sequential duplicate path raises (same
        # catch-and-translate pattern as upload_template's name collision).
        from sqlalchemy.exc import IntegrityError

        try:
            created = await self._repository.add_version_file(
                TemplateVersionFile(
                    id=file_id,
                    tenant_id=version.tenant_id,
                    version_id=version_id,
                    label=clean_label,
                    minio_path=minio_path,
                    variables=file_variables,
                    file_size=file_size,
                    position=next_position,
                )
            )
        except IntegrityError:
            raise DomainError(
                f"Ya existe un archivo relacionado con la etiqueta "
                f"'{clean_label}' en esta versión. Use una etiqueta diferente."
            )

        # Union: existing names first (order preserved, meta kept as-is),
        # genuinely new names appended with their engine-produced entries.
        union_vars = list(version.variables or [])
        union_meta = list(version.variables_meta or [])
        file_meta_by_name = {m["name"]: m for m in file_meta}
        for name in file_variables:
            if name not in union_vars:
                union_vars.append(name)
                union_meta.append(
                    file_meta_by_name.get(name, {"name": name, "contexts": []})
                )
        await self._repository.update_version_variables(
            version_id, union_vars, union_meta
        )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_FILE_ATTACH,
                resource_type="template",
                resource_id=template_id,
                details={
                    "version": version.version,
                    "version_id": str(version_id),
                    "file_id": str(file_id),
                    "label": clean_label,
                },
                ip_address=self._ip_address,
            )

        return created

    async def attach_version_file_from_example(
        self,
        template_id: UUID,
        version_id: UUID,
        *,
        label: str,
        file_bytes: bytes,
        mappings: list[dict],
        user_id: str,
        role: str = "user",
    ) -> TemplateVersionFile:
        """Attach a related file built from a FILLED example document.

        1. Rewrite the example: the engine replaces each mapped literal text
           with its {{ placeholder }}, preserving Word formatting — exact same
           contract as create_template_from_example (rewrite happens first,
           mirroring that flow).
        2. Delegate to the EXISTING attach pipeline on the rewritten bytes —
           same gates (owner-or-admin, current version only, duplicate
           label), same variables/variables_meta union, same audit. The plain
           attach path is untouched.

        Raises:
            InvalidVariableMappingError: structurally invalid mappings.
            MappingTextNotFoundError: mapping texts absent from the document
                (carries ALL missing texts).
            Plus everything attach_version_file raises (404s, access denied,
            non-current version / duplicate label DomainError, invalid docx).
        """
        rewritten_bytes = await self._engine.apply_variable_mappings(
            file_bytes, mappings
        )
        return await self.attach_version_file(
            template_id,
            version_id,
            label=label,
            file_bytes=rewritten_bytes,
            file_size=len(rewritten_bytes),
            user_id=user_id,
            role=role,
        )

    async def detach_version_file(
        self,
        template_id: UUID,
        version_id: UUID,
        file_id: UUID,
        *,
        user_id: str,
        role: str = "user",
    ) -> None:
        """Detach a related file from the template's CURRENT version.

        Recomputes the version's variables union FIRST (the PRIMARY docx is
        re-downloaded and re-extracted, the remaining files contribute their
        stored per-file variables, and variables_meta keeps the existing
        entries for surviving names, appending defaults for any missing
        name), then deletes the row + persists the union, and deletes the
        MinIO object LAST (best-effort). This ordering makes a recompute
        failure a clean abort — row and object both survive — while a failed
        MinIO delete only leaves an orphaned object behind.

        Raises: same gates as attach_version_file, plus
            TemplateVersionFileNotFoundError when the file doesn't exist or
            belongs to a different version.
        """
        template = await self._repository.get_by_id(template_id)
        if template is None:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        await self._check_access(template_id, user_uuid, role, require_owner=True)

        version = await self._repository.get_version_by_id(version_id)
        if version is None or version.template_id != template_id:
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        if version.version != template.current_version:
            raise DomainError(
                "Los archivos relacionados solo se pueden gestionar en la "
                "versión vigente de la plantilla"
            )

        file = await self._repository.get_version_file(version_id, file_id)
        if file is None:
            raise TemplateVersionFileNotFoundError(
                f"Template version file {file_id} not found"
            )

        # Recompute the union FIRST — everything fallible that touches
        # storage or the engine runs before any deletion, so a failure here
        # aborts cleanly with BOTH the row and the MinIO object intact.
        # Union source: the primary's own extraction + the remaining files'
        # stored per-file variables.
        primary_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=version.minio_path,
        )
        try:
            primary_meta = await self._engine.extract_variables(primary_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")
        primary_names = [m["name"] for m in primary_meta]

        remaining = sorted(
            [f for f in (getattr(version, "files", []) or []) if f.id != file_id],
            key=lambda f: f.position,
        )
        union_vars = list(primary_names)
        for f in remaining:
            for name in f.variables or []:
                if name not in union_vars:
                    union_vars.append(name)

        surviving = set(union_vars)
        union_meta = [
            entry
            for entry in (version.variables_meta or [])
            if _meta_entry_name(entry) in surviving
        ]
        present = {_meta_entry_name(entry) for entry in union_meta}
        primary_meta_by_name = {m["name"]: m for m in primary_meta}
        for name in union_vars:
            if name not in present:
                union_meta.append(
                    primary_meta_by_name.get(name, {"name": name, "contexts": []})
                )
                present.add(name)

        # Persist: delete the row and store the recomputed union.
        await self._repository.delete_version_file(version_id, file_id)
        await self._repository.update_version_variables(
            version_id, union_vars, union_meta
        )

        # LAST: best-effort MinIO delete of the detached object. A failure
        # here only leaves a harmless orphaned object behind.
        try:
            await self._storage.delete_file(self.TEMPLATES_BUCKET, file.minio_path)
        except Exception:
            pass  # File may already be gone

        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_FILE_DETACH,
                resource_type="template",
                resource_id=template_id,
                details={
                    "version": version.version,
                    "version_id": str(version_id),
                    "file_id": str(file_id),
                    "label": file.label,
                },
                ip_address=self._ip_address,
            )

    async def download_version_file(
        self,
        template_id: UUID,
        version_id: UUID,
        file_id: UUID,
        *,
        user_id: str,
        role: str | None,
    ) -> tuple[bytes, str]:
        """Return a related file's stored .docx bytes plus a download filename
        ``{template.name}_{label}_v{n}.docx`` (same minimal sanitization as
        download_template_version).

        Access gate mirrors download_template_version: any user with template
        access (owner, shared user, or admin).
        """
        version = await self._repository.get_version_by_id(version_id)
        if version is None or version.template_id != template_id:
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        user_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        has_access = await self._repository.has_access(
            version.template_id, user_uuid, role
        )
        if not has_access:
            raise TemplateAccessDeniedError("No tenés acceso a esta plantilla")

        file = await self._repository.get_version_file(version_id, file_id)
        if file is None:
            raise TemplateVersionFileNotFoundError(
                f"Template version file {file_id} not found"
            )

        template = await self._repository.get_by_id(version.template_id)
        if template is None:
            # FK guarantees the parent exists; defensive, non-leaking.
            raise TemplateVersionNotFoundError(
                f"Template version {version_id} not found"
            )

        file_bytes = await self._storage.download_file(
            bucket=self.TEMPLATES_BUCKET,
            path=file.minio_path,
        )

        safe_name = "".join(
            c for c in template.name if c.isalnum() or c in " _-"
        ).strip()
        safe_label = "".join(
            c for c in file.label if c.isalnum() or c in " _-"
        ).strip()
        filename = (
            f"{safe_name or 'plantilla'}_{safe_label or 'archivo'}"
            f"_v{version.version}.docx"
        )

        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            self._audit_service.log(
                actor_id=user_uuid,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_DOWNLOAD,
                resource_type="template",
                resource_id=template.id,
                details={
                    "version": version.version,
                    "version_id": str(version_id),
                    "file_id": str(file_id),
                    "label": file.label,
                },
                ip_address=self._ip_address,
            )

        return file_bytes, filename

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

    async def analyze_example(self, file_bytes: bytes) -> dict:
        """Return the document structure of an example .docx (no storage).

        Thin passthrough to the engine port — no quota check and no side
        effects. Lives on the service (instead of the router calling the
        engine directly) so the whole from-example flow is driven through
        the injected TemplateEngine port.
        """
        try:
            return await self._engine.extract_structure(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid example file: {e}")

    async def create_template_from_example(
        self,
        name: str,
        file_bytes: bytes,
        mappings: list[dict],
        tenant_id: str,
        created_by: str,
        description: str | None = None,
    ) -> dict:
        """Create a template v1 from a filled example document.

        1. Rewrite the example: the engine replaces each mapped literal text
           with its {{ placeholder }}, preserving Word formatting.
        2. Run the EXACT standard upload pipeline on the rewritten bytes
           (quota check, variable extraction, MinIO store, DB create, audit)
           by delegating to upload_template — so the created template's
           variables always come from extraction over the rewritten docx.

        Raises:
            InvalidVariableMappingError: structurally invalid mappings.
            MappingTextNotFoundError: mapping texts absent from the document
                (carries ALL missing texts).
            Plus everything upload_template raises (quota, invalid template,
            name collision).
        """
        rewritten_bytes = await self._engine.apply_variable_mappings(
            file_bytes, mappings
        )
        return await self.upload_template(
            name=name,
            file_bytes=rewritten_bytes,
            file_size=len(rewritten_bytes),
            tenant_id=tenant_id,
            created_by=created_by,
            description=description,
        )

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

        # Carry related files of the previous current version FORWARD: copy
        # each file's bytes under the new version's files/ key with a NEW id
        # (same label/variables/position), then make the new version's
        # variables/variables_meta the union of the new primary extraction
        # and the carried files — preserving the previous version's
        # user-configured meta entries for surviving names.
        old_version = await self._repository.get_version(
            uuid.UUID(template_id), new_version - 1
        )
        old_files = sorted(
            list(getattr(old_version, "files", []) or []),
            key=lambda f: f.position,
        ) if old_version is not None else []

        if old_files:
            carried_files = []
            for old_file in old_files:
                related_bytes = await self._storage.download_file(
                    bucket=self.TEMPLATES_BUCKET,
                    path=old_file.minio_path,
                )
                new_file_id = uuid.uuid4()
                new_file_path = (
                    f"{tenant_id}/{template_id}/v{new_version}/files/{new_file_id}.docx"
                )
                await self._storage.upload_file(
                    bucket=self.TEMPLATES_BUCKET,
                    path=new_file_path,
                    data=related_bytes,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                carried = await self._repository.add_version_file(
                    TemplateVersionFile(
                        id=new_file_id,
                        tenant_id=uuid.UUID(tenant_id),
                        version_id=version_id,
                        label=old_file.label,
                        minio_path=new_file_path,
                        variables=list(old_file.variables or []),
                        file_size=old_file.file_size,
                        position=old_file.position,
                    )
                )
                carried_files.append(carried)

            union_vars = list(variables)
            for carried in carried_files:
                for name in carried.variables or []:
                    if name not in union_vars:
                        union_vars.append(name)

            old_meta_by_name = {
                _meta_entry_name(entry): entry
                for entry in (getattr(old_version, "variables_meta", None) or [])
            }
            new_primary_meta_by_name = {m["name"]: m for m in variables_meta}
            union_meta = []
            for name in union_vars:
                if name in old_meta_by_name:
                    union_meta.append(old_meta_by_name[name])
                elif name in new_primary_meta_by_name:
                    union_meta.append(new_primary_meta_by_name[name])
                else:
                    union_meta.append({"name": name, "contexts": []})

            await self._repository.update_version_variables(
                version_id, union_vars, union_meta
            )
            variables = union_vars

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
        folder_id: UUID | None = None,
        folder_filter_unfiled: bool = False,
    ) -> tuple[list, int]:
        """List templates accessible to the requesting user (owned + shared + admin).

        `folder_filter_unfiled=True` restricts results to unfiled templates
        (folder_id IS NULL); `folder_id` restricts to that specific folder.
        Both are forwarded as-is to the repository, which is responsible for
        intersecting the filter with the owner/shared visibility rule.
        """
        if user_id is not None:
            uid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            return await self._repository.list_accessible(
                user_id=uid,
                role=role,
                page=page,
                size=size,
                search=search,
                folder_id=folder_id,
                folder_filter_unfiled=folder_filter_unfiled,
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

    async def update_template(
        self,
        template_id: UUID,
        user_id: UUID,
        role: str,
        *,
        name: str | None = None,
        description: str | None = None,
        description_provided: bool = False,
        folder_id: UUID | None = None,
        folder_id_provided: bool = False,
    ) -> Template:
        """Rename, update the description, and/or re-file a template.

        Access rule for name/description mirrors delete_template — owner or
        admin only. `name` is applied when not None. `description` is
        applied whenever `description_provided` is True — this allows
        explicitly clearing the description (`description=None,
        description_provided=True`), which is distinct from omitting it
        (`description_provided=False`, left unchanged). On a (tenant_id,
        name) collision, raises the same non-leaking DomainError message
        pattern used by upload_template.

        `folder_id` follows the same explicit-null pattern via
        `folder_id_provided`: setting it to None while `folder_id_provided`
        is True unfiles the template. Folders are strictly personal — unlike
        name/description, re-filing or unfiling a template has NO admin
        bypass; only the template's owner may change folder_id. When
        assigning a non-null folder_id, the target folder must exist AND
        belong to the caller, or TemplateFolderNotFoundError is raised
        (mapped by the caller to a non-leaking 404).
        """
        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        await self._check_access(template_id, user_id, role, require_owner=True)

        if folder_id_provided:
            # Strict ownership check — no admin bypass for folder assignment.
            if template.created_by != user_id:
                raise TemplateAccessDeniedError(
                    "Solo el propietario puede mover esta plantilla de carpeta"
                )
            if folder_id is not None:
                if self._folder_repository is None:
                    raise TemplateFolderNotFoundError("Carpeta no encontrada")
                folder = await self._folder_repository.get_by_id(folder_id)
                if folder is None or folder.owner_id != user_id:
                    raise TemplateFolderNotFoundError(f"Folder {folder_id} not found")

        old_name = template.name
        old_description = template.description

        try:
            updated = await self._repository.update(
                template_id,
                name=name,
                description=description,
                description_provided=description_provided,
                folder_id=folder_id,
                folder_id_provided=folder_id_provided,
            )
        except TemplateNameCollisionError:
            raise DomainError(
                f"Ya existe una plantilla con el nombre '{name}'. Use un nombre diferente."
            )

        # Audit the update
        if self._audit_service is not None:
            from app.domain.entities import AuditAction
            details = {"old_name": old_name, "new_name": updated.name}
            if description_provided:
                details["old_description"] = old_description
                details["new_description"] = updated.description
            if folder_id_provided:
                details["old_folder_id"] = str(template.folder_id) if template.folder_id else None
                details["new_folder_id"] = str(updated.folder_id) if updated.folder_id else None
            self._audit_service.log(
                actor_id=user_id,
                tenant_id=template.tenant_id,
                action=AuditAction.TEMPLATE_UPDATE,
                resource_type="template",
                resource_id=template_id,
                details=details,
                ip_address=self._ip_address,
            )

        return updated

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

        A `computed` spec on an override is validated against the FULL
        merged variables_meta (including other overrides in the same
        batch) — see `_validate_computed_meta`. A computed override's own
        `type` is normalized on save: "formula" -> "decimal", "function"
        -> "text", regardless of whatever `type` was submitted.

        Raises:
            ComputedVariableValidationError: a computed spec's `source`
                does not exist, is not numeric, is itself computed
                (chaining is unsupported in v1), or refers to itself.
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
                if override.computed is not None:
                    # Server-normalized type: computed variables' displayed
                    # type is derived from their computation kind, not from
                    # whatever the client submitted.
                    new_entry["type"] = (
                        "decimal" if override.computed.kind == "formula" else "text"
                    )
                    new_entry["computed"] = override.computed.model_dump()
                else:
                    new_entry["type"] = override.type
                    new_entry["computed"] = None
                new_entry["options"] = override.options
                new_entry["help_text"] = override.help_text
                updated_meta.append(new_entry)
            else:
                updated_meta.append(dict(entry) if isinstance(entry, dict) else {"name": entry.name, "contexts": entry.contexts})

        _validate_computed_meta(updated_meta)

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


def _meta_entry_name(entry) -> str | None:
    """Return the variable name of a variables_meta entry (dict or object)."""
    return entry.get("name") if isinstance(entry, dict) else getattr(entry, "name", None)


def _validate_computed_meta(variables_meta: list[dict]) -> None:
    """Validate every `computed` spec in `variables_meta` against the FULL
    merged meta (cross-variable rules that a single-field pydantic
    validator cannot express):

    - `source` must reference another variable that exists in this meta.
    - `source` must have type "integer" or "decimal".
    - `source` must NOT itself be computed (v1: no chaining).
    - `source` must not be the computed variable itself.

    Raises ComputedVariableValidationError (Spanish message) on the first
    violation found.
    """
    by_name = {
        (entry.get("name") if isinstance(entry, dict) else entry.name): entry
        for entry in variables_meta
    }

    for entry in variables_meta:
        computed = entry.get("computed") if isinstance(entry, dict) else getattr(entry, "computed", None)
        if not computed:
            continue

        name = entry.get("name") if isinstance(entry, dict) else entry.name
        source = computed.get("source") if isinstance(computed, dict) else computed.source

        if source == name:
            raise ComputedVariableValidationError(
                f"La variable '{name}' no puede depender de sí misma"
            )

        source_entry = by_name.get(source)
        if source_entry is None:
            raise ComputedVariableValidationError(
                f"La variable de origen '{source}' no existe en esta versión"
            )

        source_type = (
            source_entry.get("type")
            if isinstance(source_entry, dict)
            else getattr(source_entry, "type", None)
        )
        if source_type not in ("integer", "decimal"):
            raise ComputedVariableValidationError(
                f"La variable de origen '{source}' debe ser de tipo numérico "
                "(integer o decimal)"
            )

        source_computed = (
            source_entry.get("computed")
            if isinstance(source_entry, dict)
            else getattr(source_entry, "computed", None)
        )
        if source_computed:
            raise ComputedVariableValidationError(
                f"La variable de origen '{source}' no puede ser a su vez una "
                "variable calculada"
            )
