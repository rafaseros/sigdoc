from uuid import UUID

from sqlalchemy import delete as delete_stmt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.ports.document_repository import DocumentRepository as DocumentRepositoryPort
from app.infrastructure.persistence.models.document import DocumentModel
from app.infrastructure.persistence.models.template_version import TemplateVersionModel


class SQLAlchemyDocumentRepository(DocumentRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _to_orm(document) -> DocumentModel:
        """Convert a domain Document entity to a DocumentModel ORM instance."""
        from app.domain.entities import Document as DomainDocument

        if isinstance(document, DomainDocument):
            return DocumentModel(
                id=document.id,
                tenant_id=document.tenant_id,
                template_version_id=document.template_version_id,
                minio_path=document.minio_path,
                file_name=document.file_name,
                generation_type=document.generation_type,
                variables_snapshot=document.variables_snapshot,
                created_by=document.created_by,
                batch_id=document.batch_id,
                status=document.status,
                error_message=document.error_message,
            )
        # Already a DocumentModel (backwards compat)
        return document

    async def create(self, document):
        orm_doc = self._to_orm(document)
        self._session.add(orm_doc)
        await self._session.flush()
        return orm_doc

    async def create_batch(self, documents):
        orm_docs = [self._to_orm(d) for d in documents]
        self._session.add_all(orm_docs)
        await self._session.flush()
        return orm_docs

    async def get_by_id(self, document_id: UUID):
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.id == document_id)
            .options(selectinload(DocumentModel.template_version))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, document_id: UUID) -> None:
        stmt = delete_stmt(DocumentModel).where(DocumentModel.id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_paginated(
        self, page: int = 1, size: int = 20, template_id: UUID | None = None, created_by: UUID | None = None
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

        # Filter by creator (non-admin users only see their own documents)
        if created_by:
            stmt = stmt.where(DocumentModel.created_by == created_by)
            count_stmt = count_stmt.where(DocumentModel.created_by == created_by)

        # Get total count
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Apply pagination
        offset = (page - 1) * size
        stmt = stmt.order_by(DocumentModel.created_at.desc()).offset(offset).limit(size)

        result = await self._session.execute(stmt)
        documents = list(result.scalars().unique().all())

        return documents, total
