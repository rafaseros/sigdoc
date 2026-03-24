import uuid

from app.domain.exceptions import DomainError, InvalidTemplateError, TemplateNotFoundError
from app.domain.ports.storage_service import StorageService
from app.domain.ports.template_engine import TemplateEngine
from app.domain.ports.template_repository import TemplateRepository


class TemplateService:
    TEMPLATES_BUCKET = "templates"

    def __init__(
        self,
        repository: TemplateRepository,
        storage: StorageService,
        engine: TemplateEngine,
    ):
        self._repository = repository
        self._storage = storage
        self._engine = engine

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
        # 1. Extract variables (also validates it's a valid docx with Jinja2 tags)
        try:
            variables = await self._engine.extract_variables(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")

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
            file_size=file_size,
        )

        return template

    async def upload_new_version(
        self,
        template_id: str,
        file_bytes: bytes,
        file_size: int,
        tenant_id: str,
    ) -> dict:
        """
        Upload a new version of an existing template:
        1. Get the template (verify it exists)
        2. Extract variables from new file
        3. Store file in MinIO with new version number
        4. Create new TemplateVersion record
        5. Update template.current_version
        """
        from app.infrastructure.persistence.models.template_version import TemplateVersionModel

        template = await self._repository.get_by_id(uuid.UUID(template_id))
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")

        # Extract variables (also validates it's a valid docx)
        try:
            variables = await self._engine.extract_variables(file_bytes)
        except Exception as e:
            raise InvalidTemplateError(f"Invalid template file: {e}")

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

        # Create version record
        version_model = TemplateVersionModel(
            id=version_id,
            tenant_id=uuid.UUID(tenant_id),
            template_id=uuid.UUID(template_id),
            version=new_version,
            minio_path=minio_path,
            variables=variables,
            file_size=file_size,
        )
        await self._repository.create_version(version_model)

        # Update template's current_version
        template.current_version = new_version

        # Re-fetch to get updated versions list
        updated_template = await self._repository.get_by_id(uuid.UUID(template_id))

        return {
            "template": updated_template,
            "new_version": new_version,
            "variables": variables,
        }

    async def get_template(self, template_id: uuid.UUID):
        """Get template by ID with versions."""
        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        return template

    async def list_templates(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        created_by: str | None = None,
    ) -> tuple[list, int]:
        """List templates with pagination, optional search, and optional user filter."""
        from uuid import UUID as _UUID

        created_by_uuid = _UUID(created_by) if created_by else None
        return await self._repository.list_paginated(
            page=page, size=size, search=search, created_by=created_by_uuid
        )

    async def delete_template(self, template_id: uuid.UUID) -> None:
        """Delete template and all its versions from DB. MinIO files remain for now."""
        from sqlalchemy.exc import IntegrityError

        template = await self._repository.get_by_id(template_id)
        if not template:
            raise TemplateNotFoundError(f"Template {template_id} not found")
        try:
            await self._repository.delete(template_id)
        except IntegrityError:
            raise DomainError(
                "No se puede eliminar esta plantilla porque tiene documentos generados. "
                "Elimine los documentos primero."
            )
