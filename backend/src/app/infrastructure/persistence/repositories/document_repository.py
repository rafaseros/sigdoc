from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.ports.document_repository import DocumentRepository as DocumentRepositoryPort
from app.infrastructure.persistence.models.document import DocumentModel
from app.infrastructure.persistence.models.template_version import TemplateVersionModel


class SQLAlchemyDocumentRepository(DocumentRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, document):
        self._session.add(document)
        await self._session.flush()
        return document

    async def create_batch(self, documents):
        self._session.add_all(documents)
        await self._session.flush()
        return documents

    async def get_by_id(self, document_id: UUID):
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.id == document_id)
            .options(selectinload(DocumentModel.template_version))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self, page: int = 1, size: int = 20, template_id: UUID | None = None
    ) -> tuple[list, int]:
        # Base query
        stmt = select(DocumentModel).options(selectinload(DocumentModel.template_version))
        count_stmt = select(func.count()).select_from(DocumentModel)

        # Apply template filter (filter by template_id through the template_version relationship)
        if template_id:
            stmt = stmt.join(DocumentModel.template_version).where(
                TemplateVersionModel.template_id == template_id
            )
            count_stmt = count_stmt.join(TemplateVersionModel, DocumentModel.template_version_id == TemplateVersionModel.id).where(
                TemplateVersionModel.template_id == template_id
            )

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * size
        stmt = stmt.order_by(DocumentModel.created_at.desc()).offset(offset).limit(size)

        result = await self._session.execute(stmt)
        documents = list(result.scalars().unique().all())

        return documents, total
