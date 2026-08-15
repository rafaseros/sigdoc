from uuid import UUID

from sqlalchemy import delete as delete_stmt
from sqlalchemy import func, select, update as update_stmt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.entities import Document
from app.domain.ports.document_repository import DocumentRepository as DocumentRepositoryPort
from app.infrastructure.persistence.models.document import DocumentModel
from app.infrastructure.persistence.models.template_version import TemplateVersionModel

# Eager-load template_version AND its parent template in the same batched
# selectin pass — _to_entity reads both to populate the enrichment fields
# without per-row lazy loads (no N+1).
_EAGER_TEMPLATE_VERSION = selectinload(DocumentModel.template_version).selectinload(
    TemplateVersionModel.template
)


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
                docx_minio_path=document.docx_minio_path,
                docx_file_name=document.docx_file_name,
                pdf_file_name=document.pdf_file_name,
                pdf_minio_path=document.pdf_minio_path,
                generation_type=document.generation_type,
                variables_snapshot=document.variables_snapshot,
                created_by=document.created_by,
                batch_id=document.batch_id,
                group_id=document.group_id,
                related_label=document.related_label,
                group_position=document.group_position,
                status=document.status,
                error_message=document.error_message,
            )
        # Already a DocumentModel (backwards compat)
        return document

    @staticmethod
    def _to_entity(model: DocumentModel) -> Document:
        """Convert a DocumentModel (with template_version eagerly loaded) to a
        domain Document, populating the template enrichment fields from the
        template_versions → templates join."""
        version = model.template_version
        return Document(
            id=model.id,
            tenant_id=model.tenant_id,
            template_version_id=model.template_version_id,
            docx_file_name=model.docx_file_name,
            docx_minio_path=model.docx_minio_path,
            generation_type=model.generation_type,
            variables_snapshot=model.variables_snapshot,
            created_by=model.created_by,
            pdf_file_name=model.pdf_file_name,
            pdf_minio_path=model.pdf_minio_path,
            batch_id=model.batch_id,
            group_id=model.group_id,
            related_label=model.related_label,
            group_position=model.group_position,
            status=model.status,
            error_message=model.error_message,
            created_at=model.created_at,
            template_id=version.template_id if version is not None else None,
            template_name=(
                version.template.name
                if version is not None and version.template is not None
                else None
            ),
            template_version=version.version if version is not None else None,
        )

    async def create(self, document):
        orm_doc = self._to_orm(document)
        self._session.add(orm_doc)
        await self._session.flush()
        # Re-fetch with eager-loaded relationships so the returned entity
        # carries the template enrichment fields (single extra SELECT —
        # same pattern as update_pdf_fields).
        return await self.get_by_id(orm_doc.id)

    async def create_batch(self, documents):
        orm_docs = [self._to_orm(d) for d in documents]
        self._session.add_all(orm_docs)
        await self._session.flush()
        # Callers ignore the return value (generate_bulk builds its response
        # from its own domain entities); return the input for parity with the
        # fake repository.
        return documents

    async def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.id == document_id)
            .options(_EAGER_TEMPLATE_VERSION)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def delete(self, document_id: UUID) -> None:
        stmt = delete_stmt(DocumentModel).where(DocumentModel.id == document_id)
        await self._session.execute(stmt)
        await self._session.flush()

    async def update_pdf_fields(
        self, doc_id: UUID, pdf_file_name: str, pdf_minio_path: str
    ) -> Document:
        """Update the PDF file fields on an existing document row.

        Issues a single UPDATE statement, then re-fetches the row so the
        caller always gets a fully-loaded domain entity (including the
        template enrichment fields).

        Used exclusively by DocumentService.ensure_pdf (Phase 3).
        """
        stmt = (
            update_stmt(DocumentModel)
            .where(DocumentModel.id == doc_id)
            .values(pdf_file_name=pdf_file_name, pdf_minio_path=pdf_minio_path)
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Re-fetch with eager-loaded relationships
        fetch_stmt = (
            select(DocumentModel)
            .where(DocumentModel.id == doc_id)
            .options(_EAGER_TEMPLATE_VERSION)
        )
        result = await self._session.execute(fetch_stmt)
        return self._to_entity(result.scalar_one())

    async def list_by_batch_id(self, batch_id: UUID, tenant_id: UUID) -> list:
        """Return all documents for a given batch_id scoped to tenant_id.

        Issues a single SELECT WHERE batch_id = :batch_id AND tenant_id = :tenant_id.
        O(batch_size) — avoids the O(N total tenant docs) scan of list_paginated.
        Eager-loads template_version (and its template) so entities carry the
        enrichment fields without additional queries (matches get_by_id /
        list_paginated pattern). W-PRES-02 fix.
        """
        stmt = (
            select(DocumentModel)
            .where(
                DocumentModel.batch_id == batch_id,
                DocumentModel.tenant_id == tenant_id,
            )
            .options(_EAGER_TEMPLATE_VERSION)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def list_by_group_id(self, group_id: UUID, tenant_id: UUID) -> list:
        """Return all documents for a given group_id scoped to tenant_id.

        Ordered by (group_position, created_at, id): the primary (position 0)
        first, then related files in render order. Old pre-migration grouped
        rows all have group_position 0, so created_at keeps them primary-first
        by creation. Used by the combined ZIP download endpoint.
        """
        stmt = (
            select(DocumentModel)
            .where(
                DocumentModel.group_id == group_id,
                DocumentModel.tenant_id == tenant_id,
            )
            .options(_EAGER_TEMPLATE_VERSION)
            .order_by(
                DocumentModel.group_position.asc(),
                DocumentModel.created_at.asc(),
                DocumentModel.id.asc(),
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().unique().all()]

    async def list_document_groups(
        self,
        page: int = 1,
        size: int = 20,
        template_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list, int]:
        """List documents grouped by generation, paginated by the GROUP unit.

        The group unit is COALESCE(group_id, id): a multi-file generation is
        one group; a standalone document is its own single-member group.

        Two-step query:
          1. Select the PAGE of group units (grouped by COALESCE key, ordered
             by the group's latest created_at DESC) plus the total distinct
             group count.
          2. Fetch every document belonging to those page group units, ordered
             by (group_position, created_at, id), and bucket them back into
             groups preserving the page order.
        """
        group_key = func.coalesce(DocumentModel.group_id, DocumentModel.id)

        keys_stmt = select(group_key.label("group_key"))
        count_stmt = select(func.count(func.distinct(group_key)))

        if template_id:
            keys_stmt = keys_stmt.join(
                TemplateVersionModel,
                DocumentModel.template_version_id == TemplateVersionModel.id,
            ).where(TemplateVersionModel.template_id == template_id)
            count_stmt = count_stmt.join(
                TemplateVersionModel,
                DocumentModel.template_version_id == TemplateVersionModel.id,
            ).where(TemplateVersionModel.template_id == template_id)

        if created_by:
            keys_stmt = keys_stmt.where(DocumentModel.created_by == created_by)
            count_stmt = count_stmt.where(DocumentModel.created_by == created_by)

        total = (await self._session.execute(count_stmt)).scalar_one()

        offset = (page - 1) * size
        keys_stmt = (
            keys_stmt.group_by(group_key)
            .order_by(func.max(DocumentModel.created_at).desc())
            .offset(offset)
            .limit(size)
        )
        key_rows = (await self._session.execute(keys_stmt)).all()
        group_keys = [row.group_key for row in key_rows]

        if not group_keys:
            return [], total

        docs_stmt = (
            select(DocumentModel)
            .where(group_key.in_(group_keys))
            .options(_EAGER_TEMPLATE_VERSION)
            .order_by(
                DocumentModel.group_position.asc(),
                DocumentModel.created_at.asc(),
                DocumentModel.id.asc(),
            )
        )
        result = await self._session.execute(docs_stmt)
        models = result.scalars().unique().all()

        # Bucket documents back into groups, preserving the page's group order.
        buckets: dict = {}
        for m in models:
            key = m.group_id if m.group_id is not None else m.id
            buckets.setdefault(key, []).append(self._to_entity(m))

        groups = [buckets[key] for key in group_keys if key in buckets]
        return groups, total

    async def list_paginated(
        self, page: int = 1, size: int = 20, template_id: UUID | None = None, created_by: UUID | None = None
    ) -> tuple[list, int]:
        # Base query
        stmt = select(DocumentModel).options(_EAGER_TEMPLATE_VERSION)
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
        documents = [self._to_entity(m) for m in result.scalars().unique().all()]

        return documents, total
