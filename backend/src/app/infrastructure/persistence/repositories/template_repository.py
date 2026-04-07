from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.ports.template_repository import TemplateRepository as TemplateRepositoryPort
from app.infrastructure.persistence.models.template import TemplateModel
from app.infrastructure.persistence.models.template_version import TemplateVersionModel


class SQLAlchemyTemplateRepository(TemplateRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, template):
        self._session.add(template)
        await self._session.flush()
        return template

    async def get_by_id(self, template_id: UUID):
        stmt = (
            select(TemplateModel)
            .where(TemplateModel.id == template_id)
            .options(selectinload(TemplateModel.versions))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list, int]:
        # Base query
        stmt = select(TemplateModel).options(selectinload(TemplateModel.versions))
        count_stmt = select(func.count()).select_from(TemplateModel)

        # Apply search filter
        if search:
            search_filter = TemplateModel.name.ilike(f"%{search}%")
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        # Apply created_by filter (non-admin users only see their own templates)
        if created_by is not None:
            created_by_filter = TemplateModel.created_by == created_by
            stmt = stmt.where(created_by_filter)
            count_stmt = count_stmt.where(created_by_filter)

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * size
        stmt = stmt.order_by(TemplateModel.created_at.desc()).offset(offset).limit(size)

        result = await self._session.execute(stmt)
        templates = list(result.scalars().unique().all())

        return templates, total

    async def delete(self, template_id: UUID) -> None:
        stmt = delete(TemplateModel).where(TemplateModel.id == template_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def create_version(self, version):
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_version(self, template_id: UUID, version: int):
        stmt = select(TemplateVersionModel).where(
            TemplateVersionModel.template_id == template_id,
            TemplateVersionModel.version == version,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_version_by_id(self, version_id: UUID):
        stmt = select(TemplateVersionModel).where(
            TemplateVersionModel.id == version_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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
    ) -> TemplateModel:
        """Create a template and its first version atomically."""
        template = TemplateModel(
            id=template_id,
            tenant_id=tenant_id,
            name=name,
            description=description,
            current_version=version,
            created_by=created_by,
        )
        self._session.add(template)
        await self._session.flush()

        version_model = TemplateVersionModel(
            id=version_id,
            tenant_id=tenant_id,
            template_id=template_id,
            version=version,
            minio_path=minio_path,
            variables=variables,
            variables_meta=variables_meta or [],
            file_size=file_size,
        )
        self._session.add(version_model)
        await self._session.flush()

        # Refresh to load the versions relationship
        await self._session.refresh(template, ["versions"])
        return template
