"""Unit tests for FakeDocumentRepository.list_by_batch_id (W-PRES-02 fix).

TDD RED phase: these tests MUST fail before list_by_batch_id is implemented.

Scenarios:
- Returns all docs for a given batch_id + tenant_id
- Returns empty list when batch_id matches but tenant_id doesn't (tenant isolation)
- Returns empty list when batch_id doesn't match
- Returns only docs with matching batch_id when repository has mixed data
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Document
from tests.fakes import FakeDocumentRepository

TENANT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
BATCH_1 = uuid.UUID("00000000-0001-0001-0001-000000000001")
BATCH_2 = uuid.UUID("00000000-0002-0002-0002-000000000002")


def _make_doc(
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID | None = None,
) -> Document:
    doc_id = uuid.uuid4()
    return Document(
        id=doc_id,
        tenant_id=tenant_id,
        template_version_id=uuid.uuid4(),
        docx_file_name=f"{doc_id}.docx",
        docx_minio_path=f"{tenant_id}/{doc_id}.docx",
        generation_type="bulk" if batch_id is not None else "single",
        variables_snapshot={},
        created_by=uuid.uuid4(),
        batch_id=batch_id,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_list_by_batch_id_returns_matching_docs():
    """Returns all documents matching batch_id + tenant_id."""
    repo = FakeDocumentRepository()
    doc1 = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_1)
    doc2 = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_1)
    doc3 = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_2)  # different batch — excluded
    for d in (doc1, doc2, doc3):
        await repo.create(d)

    result = await repo.list_by_batch_id(batch_id=BATCH_1, tenant_id=TENANT_A)

    assert len(result) == 2
    ids = {d.id for d in result}
    assert doc1.id in ids
    assert doc2.id in ids
    assert doc3.id not in ids


@pytest.mark.asyncio
async def test_list_by_batch_id_tenant_isolation():
    """Does NOT return docs from a different tenant even if batch_id matches."""
    repo = FakeDocumentRepository()
    doc_a = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_1)
    doc_b = _make_doc(tenant_id=TENANT_B, batch_id=BATCH_1)  # same batch, different tenant
    await repo.create(doc_a)
    await repo.create(doc_b)

    result = await repo.list_by_batch_id(batch_id=BATCH_1, tenant_id=TENANT_A)

    assert len(result) == 1
    assert result[0].id == doc_a.id


@pytest.mark.asyncio
async def test_list_by_batch_id_returns_empty_for_unknown_batch():
    """Returns an empty list when no docs match the batch_id."""
    repo = FakeDocumentRepository()
    doc = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_1)
    await repo.create(doc)

    result = await repo.list_by_batch_id(batch_id=BATCH_2, tenant_id=TENANT_A)

    assert result == []


@pytest.mark.asyncio
async def test_list_by_batch_id_excludes_single_docs():
    """Does NOT return docs without a batch_id (single-generation docs)."""
    repo = FakeDocumentRepository()
    single_doc = _make_doc(tenant_id=TENANT_A, batch_id=None)
    bulk_doc = _make_doc(tenant_id=TENANT_A, batch_id=BATCH_1)
    await repo.create(single_doc)
    await repo.create(bulk_doc)

    result = await repo.list_by_batch_id(batch_id=BATCH_1, tenant_id=TENANT_A)

    assert len(result) == 1
    assert result[0].id == bulk_doc.id
