from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import Document
from app.domain.ports.document_repository import DocumentRepository


class FakeDocumentRepository(DocumentRepository):
    """Dict-backed in-memory implementation of DocumentRepository for testing."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}

    async def create(self, document: Document) -> Document:
        # Simulate DB-assigned created_at so API responses pass schema validation
        if document.created_at is None:
            document.created_at = datetime.now(timezone.utc)
        self._documents[document.id] = document
        return document

    async def create_batch(self, documents: list[Document]) -> list[Document]:
        now = datetime.now(timezone.utc)
        for doc in documents:
            if doc.created_at is None:
                doc.created_at = now
            self._documents[doc.id] = doc
        return documents

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return self._documents.get(document_id)

    async def delete(self, document_id: UUID) -> None:
        self._documents.pop(document_id, None)

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        template_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[Document], int]:
        items = list(self._documents.values())

        if template_id is not None:
            # Filter by template_version_id is not directly possible without joining;
            # the fake stores Documents directly so we match on template_version_id
            # that was set on the document (tests must set this to the correct version id).
            # For tests that need template_id filtering, the caller should use
            # the version_id from the template version.
            items = [d for d in items if d.template_version_id == template_id]

        if created_by is not None:
            items = [d for d in items if d.created_by == created_by]

        total = len(items)
        offset = (page - 1) * size
        page_items = items[offset : offset + size]

        return page_items, total
