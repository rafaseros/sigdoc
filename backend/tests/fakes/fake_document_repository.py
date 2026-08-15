from datetime import datetime, timezone
from uuid import UUID

from app.domain.entities import Document
from app.domain.ports.document_repository import DocumentRepository


class FakeDocumentRepository(DocumentRepository):
    """Dict-backed in-memory implementation of DocumentRepository for testing."""

    def __init__(self) -> None:
        self._documents: dict[UUID, Document] = {}
        self._update_pdf_fields_calls: list[dict] = []  # call recorder for assertions
        # Maps template_version_id → template_id so list_paginated can filter by template_id
        self._version_to_template: dict[UUID, UUID] = {}
        # Maps template_version_id → (template_name, version_number) so reads
        # can enrich documents like the real repo's join does
        self._version_info: dict[UUID, tuple[str | None, int | None]] = {}

    def register_template_version(
        self,
        version_id: UUID,
        template_id: UUID,
        template_name: str | None = None,
        version_number: int | None = None,
    ) -> None:
        """Register the template info for a given version_id.

        Call this in test setup after seeding a template version so that
        list_paginated can correctly filter documents by template_id, and —
        when template_name/version_number are given — so reads enrich
        documents with template_id/template_name/template_version (mirrors
        the real repository's read-time join).
        """
        self._version_to_template[version_id] = template_id
        self._version_info[version_id] = (template_name, version_number)

    def _enrich(self, doc: Document | None) -> Document | None:
        """Fill missing enrichment fields from the registered version info."""
        if doc is None:
            return None
        template_id = self._version_to_template.get(doc.template_version_id)
        if template_id is not None and doc.template_id is None:
            doc.template_id = template_id
        name, number = self._version_info.get(doc.template_version_id, (None, None))
        if name is not None and doc.template_name is None:
            doc.template_name = name
        if number is not None and doc.template_version is None:
            doc.template_version = number
        return doc

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
        return self._enrich(self._documents.get(document_id))

    async def delete(self, document_id: UUID) -> None:
        self._documents.pop(document_id, None)

    async def update_pdf_fields(
        self, doc_id: UUID, pdf_file_name: str, pdf_minio_path: str
    ) -> Document:
        """Update pdf_file_name and pdf_minio_path on the stored document."""
        self._update_pdf_fields_calls.append(
            {"doc_id": doc_id, "pdf_file_name": pdf_file_name, "pdf_minio_path": pdf_minio_path}
        )
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Document {doc_id} not found in fake repository")
        # Dataclass is mutable — update in-place
        doc.pdf_file_name = pdf_file_name
        doc.pdf_minio_path = pdf_minio_path
        return doc

    async def list_by_batch_id(self, batch_id: UUID, tenant_id: UUID) -> list[Document]:
        """Return all documents for the given batch_id scoped to tenant_id.

        In-memory filter: O(total docs in fake repo) — acceptable for tests.
        Matches documents where batch_id == batch_id AND tenant_id == tenant_id.
        """
        return [
            self._enrich(d)
            for d in self._documents.values()
            if d.batch_id == batch_id and d.tenant_id == tenant_id
        ]

    def _matches_template(self, doc: Document, template_id: UUID) -> bool:
        """True if doc belongs to template_id.

        Resolves template_version_id → template_id via the registered mapping;
        falls back to direct comparison for legacy tests that set
        template_version_id to the template UUID.
        """
        mapped = self._version_to_template.get(doc.template_version_id)
        if mapped is not None:
            return mapped == template_id
        return doc.template_version_id == template_id

    async def list_paginated(
        self,
        page: int = 1,
        size: int = 20,
        template_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[Document], int]:
        items = list(self._documents.values())

        if template_id is not None:
            items = [d for d in items if self._matches_template(d, template_id)]

        if created_by is not None:
            items = [d for d in items if d.created_by == created_by]

        total = len(items)
        offset = (page - 1) * size
        page_items = [self._enrich(d) for d in items[offset : offset + size]]

        return page_items, total

    async def list_by_group_id(self, group_id: UUID, tenant_id: UUID) -> list[Document]:
        """Return documents for group_id scoped to tenant_id, primary-first.

        Ordered by (group_position, created_at, id). Standalone documents
        (group_id None) are never returned.
        """
        _EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
        docs = [
            d
            for d in self._documents.values()
            if d.group_id == group_id and d.tenant_id == tenant_id
        ]
        docs.sort(key=lambda d: (d.group_position, d.created_at or _EPOCH, str(d.id)))
        return [self._enrich(d) for d in docs]

    async def list_document_groups(
        self,
        page: int = 1,
        size: int = 20,
        template_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> tuple[list[list[Document]], int]:
        """Group documents by COALESCE(group_id, id), paginated by group unit.

        Groups ordered by latest created_at DESC; each group's documents
        ordered by (group_position, created_at, id).
        """
        _EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
        items = list(self._documents.values())

        if template_id is not None:
            items = [d for d in items if self._matches_template(d, template_id)]
        if created_by is not None:
            items = [d for d in items if d.created_by == created_by]

        buckets: dict = {}
        for d in items:
            key = d.group_id if d.group_id is not None else d.id
            buckets.setdefault(key, []).append(d)

        # Order group units by their latest created_at DESC.
        def _latest(key):
            return max((d.created_at or _EPOCH) for d in buckets[key])

        ordered_keys = sorted(buckets.keys(), key=_latest, reverse=True)
        total = len(ordered_keys)

        offset = (page - 1) * size
        page_keys = ordered_keys[offset : offset + size]

        groups: list[list[Document]] = []
        for key in page_keys:
            members = sorted(
                buckets[key],
                key=lambda d: (d.group_position, d.created_at or _EPOCH, str(d.id)),
            )
            groups.append([self._enrich(d) for d in members])
        return groups, total
