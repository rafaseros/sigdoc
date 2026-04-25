from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities import Document


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, document: Document) -> Document:
        ...

    @abstractmethod
    async def create_batch(self, documents: list[Document]) -> list[Document]:
        ...

    @abstractmethod
    async def get_by_id(self, document_id: UUID) -> Document | None:
        ...

    @abstractmethod
    async def delete(self, document_id: UUID) -> None:
        ...

    @abstractmethod
    async def list_paginated(
        self, page: int = 1, size: int = 20, template_id: UUID | None = None, created_by: UUID | None = None
    ) -> tuple[list[Document], int]:
        ...

    @abstractmethod
    async def update_pdf_fields(
        self, doc_id: UUID, pdf_file_name: str, pdf_minio_path: str
    ) -> Document:
        """Update the PDF file fields on an existing document row.

        Returns the updated domain entity.
        Used exclusively by DocumentService.ensure_pdf.
        """
        ...

    @abstractmethod
    async def list_by_batch_id(self, batch_id: UUID, tenant_id: UUID) -> list[Document]:
        """Return all documents belonging to a given batch, scoped to a tenant.

        Filters by batch_id AND tenant_id for correctness and security.
        O(batch_size) — does NOT scan the full tenant document table.
        Used by the bulk download endpoint (W-PRES-02 fix).
        """
        ...
