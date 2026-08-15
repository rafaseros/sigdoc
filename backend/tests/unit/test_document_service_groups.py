"""Unit tests for grouped documents (Feature #4, Phase A).

Covers:
- generate_single / generate_bulk set related_label + group_position:
  primary → (None, 0); related file i (1-based) → (label, i).
- repo/service list_document_groups: pagination UNIT is the group
  (COALESCE(group_id, id)); groups ordered by latest created_at DESC; docs
  within a group ordered by (group_position, created_at, id); a standalone
  document is its own single-member group with group_id None.

Strict TDD: written first (RED), then the service/repo are updated (GREEN).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.application.services.document_service import DocumentService
from app.domain.entities import Document, Template, TemplateVersion, TemplateVersionFile
from tests.fakes import (
    FakeDocumentRepository,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


PRIMARY_BYTES = b"primary-docx-bytes"


def make_service(doc_repo, tpl_repo, storage, engine) -> DocumentService:
    return DocumentService(
        document_repository=doc_repo,
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
    )


def seed_version_with_files(tpl_repo, storage, labels=None, variables=None):
    if variables is None:
        variables = ["name", "company"]
    labels = labels or []

    tenant_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=tenant_id,
        template_id=template_id,
        version=1,
        minio_path=f"{tenant_id}/{template_id}/v1/template.docx",
        variables=variables,
        created_at=now,
    )
    tpl_repo._versions[version_id] = version

    template = Template(
        id=template_id,
        tenant_id=tenant_id,
        name="Multi Template",
        description=None,
        current_version=1,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    tpl_repo._templates[template_id] = template
    storage.files[("templates", version.minio_path)] = PRIMARY_BYTES

    for i, label in enumerate(labels):
        file_id = uuid.uuid4()
        minio_path = f"{tenant_id}/{template_id}/v1/files/{file_id}.docx"
        file = TemplateVersionFile(
            id=file_id,
            tenant_id=tenant_id,
            version_id=version_id,
            label=label,
            minio_path=minio_path,
            variables=variables,
            file_size=10,
            position=i,
            created_at=now,
        )
        version.files.append(file)
        tpl_repo._version_files[(version_id, file_id)] = file
        storage.files[("templates", minio_path)] = f"related-{label}".encode()

    return version, str(version_id), str(tenant_id), str(owner_id), template_id


# ---------------------------------------------------------------------------
# generate_single / generate_bulk — related_label + group_position
# ---------------------------------------------------------------------------


class TestGenerateSetsLabelAndPosition:
    async def test_single_primary_none_related_1_based(
        self, fake_document_repo, fake_template_repo, fake_storage
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, FakeTemplateEngine()
        )
        _, version_id, tenant_id, user_id, _ = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo", "Factura"]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )
        docs = result["documents"]

        assert (docs[0].related_label, docs[0].group_position) == (None, 0)
        assert (docs[1].related_label, docs[1].group_position) == ("Recibo", 1)
        assert (docs[2].related_label, docs[2].group_position) == ("Factura", 2)

    async def test_single_standalone_primary_none_zero(
        self, fake_document_repo, fake_template_repo, fake_storage
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, FakeTemplateEngine()
        )
        _, version_id, tenant_id, user_id, _ = seed_version_with_files(
            fake_template_repo, fake_storage, labels=[]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )
        doc = result["documents"][0]
        assert doc.related_label is None
        assert doc.group_position == 0

    async def test_bulk_each_row_primary_none_related_1_based(
        self, fake_document_repo, fake_template_repo, fake_storage
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, FakeTemplateEngine()
        )
        _, version_id, tenant_id, user_id, _ = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        await service.generate_bulk(
            template_version_id=version_id,
            rows=[{"name": "Alice", "company": "ACME"}, {"name": "Bob", "company": "C"}],
            tenant_id=tenant_id,
            created_by=user_id,
        )

        docs = list(fake_document_repo._documents.values())
        # Group per row: each row has one primary (None, 0) and one related (label, 1)
        primaries = [d for d in docs if d.group_position == 0]
        related = [d for d in docs if d.group_position == 1]
        assert len(primaries) == 2 and len(related) == 2
        assert all(d.related_label is None for d in primaries)
        assert all(d.related_label == "Recibo" for d in related)


# ---------------------------------------------------------------------------
# list_document_groups — repo + service semantics
# ---------------------------------------------------------------------------


def _insert_group(repo, *, tenant_id, created_by, template_version_id, labels, base_time):
    """Insert a primary + related documents sharing one group_id directly."""
    group_id = uuid.uuid4()
    docs = []
    # primary
    for pos, label in enumerate([None, *labels]):
        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            template_version_id=template_version_id,
            docx_file_name=f"doc_{pos}.docx",
            docx_minio_path=f"{tenant_id}/{group_id}/doc_{pos}.docx",
            pdf_file_name=f"doc_{pos}.pdf",
            pdf_minio_path=f"{tenant_id}/{group_id}/doc_{pos}.pdf",
            generation_type="single",
            group_id=group_id,
            related_label=label,
            group_position=pos,
            variables_snapshot={"name": "x"},
            created_by=created_by,
            status="completed",
            created_at=base_time + timedelta(seconds=pos),
        )
        repo._documents[doc.id] = doc
        docs.append(doc)
    return group_id, docs


def _insert_standalone(repo, *, tenant_id, created_by, template_version_id, base_time):
    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        template_version_id=template_version_id,
        docx_file_name="solo.docx",
        docx_minio_path=f"{tenant_id}/{uuid.uuid4()}/solo.docx",
        pdf_file_name="solo.pdf",
        pdf_minio_path=f"{tenant_id}/{uuid.uuid4()}/solo.pdf",
        generation_type="single",
        group_id=None,
        related_label=None,
        group_position=0,
        variables_snapshot={"name": "x"},
        created_by=created_by,
        status="completed",
        created_at=base_time,
    )
    repo._documents[doc.id] = doc
    return doc


class TestListDocumentGroups:
    async def test_group_returns_primary_and_related_in_order(
        self, fake_document_repo
    ):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        tv_id = uuid.uuid4()
        base = datetime.now(timezone.utc)
        group_id, _ = _insert_group(
            fake_document_repo,
            tenant_id=tenant_id,
            created_by=user_id,
            template_version_id=tv_id,
            labels=["Recibo", "Factura"],
            base_time=base,
        )

        service = make_service(
            fake_document_repo, FakeTemplateRepository(), FakeStorageService(),
            FakeTemplateEngine(),
        )
        groups, total = await service.list_document_groups(page=1, size=20)

        assert total == 1
        assert len(groups) == 1
        members = groups[0]
        assert len(members) == 3
        assert [m.group_position for m in members] == [0, 1, 2]
        assert [m.related_label for m in members] == [None, "Recibo", "Factura"]
        assert all(m.group_id == group_id for m in members)

    async def test_standalone_is_single_member_group_none(self, fake_document_repo):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        base = datetime.now(timezone.utc)
        doc = _insert_standalone(
            fake_document_repo,
            tenant_id=tenant_id,
            created_by=user_id,
            template_version_id=uuid.uuid4(),
            base_time=base,
        )

        service = make_service(
            fake_document_repo, FakeTemplateRepository(), FakeStorageService(),
            FakeTemplateEngine(),
        )
        groups, total = await service.list_document_groups(page=1, size=20)

        assert total == 1
        assert len(groups) == 1 and len(groups[0]) == 1
        assert groups[0][0].id == doc.id
        assert groups[0][0].group_id is None

    async def test_pagination_unit_is_the_group(self, fake_document_repo):
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        base = datetime.now(timezone.utc)
        # 3 group units: 1 grouped (2 docs) + 2 standalone
        _insert_group(
            fake_document_repo,
            tenant_id=tenant_id,
            created_by=user_id,
            template_version_id=uuid.uuid4(),
            labels=["Recibo"],
            base_time=base,
        )
        _insert_standalone(
            fake_document_repo, tenant_id=tenant_id, created_by=user_id,
            template_version_id=uuid.uuid4(), base_time=base + timedelta(minutes=1),
        )
        _insert_standalone(
            fake_document_repo, tenant_id=tenant_id, created_by=user_id,
            template_version_id=uuid.uuid4(), base_time=base + timedelta(minutes=2),
        )

        service = make_service(
            fake_document_repo, FakeTemplateRepository(), FakeStorageService(),
            FakeTemplateEngine(),
        )
        page1, total = await service.list_document_groups(page=1, size=2)
        page2, total2 = await service.list_document_groups(page=2, size=2)

        assert total == 3 and total2 == 3
        assert len(page1) == 2
        assert len(page2) == 1

    async def test_created_by_scope_filters_groups(self, fake_document_repo):
        tenant_id = uuid.uuid4()
        me = uuid.uuid4()
        other = uuid.uuid4()
        base = datetime.now(timezone.utc)
        _insert_group(
            fake_document_repo, tenant_id=tenant_id, created_by=me,
            template_version_id=uuid.uuid4(), labels=["Recibo"], base_time=base,
        )
        _insert_group(
            fake_document_repo, tenant_id=tenant_id, created_by=other,
            template_version_id=uuid.uuid4(), labels=["Recibo"], base_time=base,
        )

        service = make_service(
            fake_document_repo, FakeTemplateRepository(), FakeStorageService(),
            FakeTemplateEngine(),
        )
        # No scope (admin) → 2 groups; scoped to me → 1 group
        _, total_all = await service.list_document_groups(page=1, size=20)
        mine, total_mine = await service.list_document_groups(
            page=1, size=20, created_by=str(me)
        )
        assert total_all == 2
        assert total_mine == 1
        assert all(m.created_by == me for m in mine[0])
