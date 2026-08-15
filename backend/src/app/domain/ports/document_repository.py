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

    @abstractmethod
    async def list_by_group_id(self, group_id: UUID, tenant_id: UUID) -> list[Document]:
        """Return all documents belonging to a given group, scoped to a tenant.

        Filters by group_id AND tenant_id. Ordered by
        (group_position, created_at, id) so the primary comes first and related
        files follow in render order. Used by the combined ZIP download
        endpoint. A standalone document (group_id NULL) is never returned.
        """
        ...

    @abstractmethod
    async def list_document_groups(
        self,
        page: int = 1,
        size: int = 20,
        template_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[list[Document]], int]:
        """List documents grouped by generation, paginated by the GROUP unit.

        The pagination unit is COALESCE(group_id, id): a multi-file generation
        counts as one group; a standalone document is its own single-member
        group. Groups are ordered by their latest created_at DESC. Each group's
        documents are ordered by (group_position, created_at, id).

        Returns (groups, total_groups) where total_groups is the number of
        distinct group units matching the filters.
        """
        ...
