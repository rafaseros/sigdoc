"""Unit tests for multi-file document generation (Tanda 3).

A template version can carry N related docx files that share the primary's
variable set. Generating fills the variables ONCE and renders ALL files:
- generate_single → N Document rows sharing one group_id (None when the
  version has no related files — existing behavior unchanged).
- preview(file_id=...) previews a related file instead of the primary.
- generate_bulk → one Document row per file per Excel row; group_id shared
  PER ROW; batch_id shared across the whole batch.

Strict TDD: written first (RED), then DocumentService is updated (GREEN).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.application.services.document_service import DocumentService
from app.domain.entities import Template, TemplateVersion, TemplateVersionFile
from app.domain.entities.subscription_tier import FREE_TIER_ID
from app.domain.exceptions import (
    PdfConversionError,
    QuotaExceededError,
    TemplateVersionFileNotFoundError,
)
from tests.fakes import (
    FakeDocumentRepository,
    FakePdfConverter,
    FakeQuotaService,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PRIMARY_BYTES = b"primary-docx-bytes"


class RecordingEngine(FakeTemplateEngine):
    """Records (file_bytes, variables) for every render call."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.render_calls: list[tuple[bytes, dict]] = []

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        self.render_calls.append((file_bytes, dict(variables)))
        return await super().render(file_bytes, variables)


def make_service(
    doc_repo: FakeDocumentRepository,
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
    pdf_converter: FakePdfConverter | None = None,
) -> DocumentService:
    return DocumentService(
        document_repository=doc_repo,
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
        pdf_converter=pdf_converter,
    )


def seed_version_with_files(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    labels: list[str] | None = None,
    variables: list[str] | None = None,
) -> tuple[TemplateVersion, str, str, str]:
    """Seed template + version (+ N related files) in the fakes.

    Returns (version, version_id_str, tenant_id_str, owner_id_str).
    """
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

    return version, str(version_id), str(tenant_id), str(owner_id)


# ---------------------------------------------------------------------------
# generate_single — multi-file
# ---------------------------------------------------------------------------


class TestGenerateSingleMultiFile:
    async def test_creates_one_document_per_file_primary_first(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo de pago", "Factura"]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        docs = result["documents"]
        assert len(docs) == 3
        assert len(fake_document_repo._documents) == 3

        # Primary first, then related files by position
        assert docs[0].docx_file_name == "Alice.docx"
        assert docs[1].docx_file_name == "Alice_Recibo_de_pago.docx"
        assert docs[2].docx_file_name == "Alice_Factura.docx"

    async def test_group_id_shared_across_all_documents(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        group_id = result["group_id"]
        assert group_id is not None
        for doc in result["documents"]:
            assert doc.group_id == group_id

    async def test_single_file_version_unchanged_group_id_none(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=[]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert result["group_id"] is None
        assert len(result["documents"]) == 1
        doc = result["documents"][0]
        assert doc.group_id is None
        assert doc.docx_file_name == "Alice.docx"

    async def test_each_file_rendered_with_same_resolved_context(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        version, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert len(engine.render_calls) == 2
        assert engine.render_calls[0][0] == PRIMARY_BYTES
        assert engine.render_calls[1][0] == b"related-Recibo"
        assert engine.render_calls[0][1] == engine.render_calls[1][1]

    async def test_atomic_rollback_when_later_file_pdf_fails(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """When the RELATED file's PDF conversion fails, every already-uploaded
        key (primary DOCX + primary PDF + related DOCX) is deleted and zero DB
        rows are persisted."""
        call_count = 0

        class FailOnSecondCall(FakePdfConverter):
            async def convert(self, docx_bytes: bytes) -> bytes:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise PdfConversionError("related file conversion failed")
                return self.convert_result

        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter=FailOnSecondCall(),
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        with pytest.raises(PdfConversionError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert doc_files == [], f"expected full rollback, found {doc_files}"
        assert len(fake_document_repo._documents) == 0


# ---------------------------------------------------------------------------
# quota — must count the PRIMARY plus every related file
# ---------------------------------------------------------------------------


def make_service_with_quota(
    doc_repo: FakeDocumentRepository,
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
    quota: FakeQuotaService,
) -> DocumentService:
    return DocumentService(
        document_repository=doc_repo,
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
        quota_service=quota,
        tier_id=FREE_TIER_ID,
    )


class TestQuotaCountsRelatedFiles:
    """check_document_quota must be charged 1 + N (N = related files) BEFORE
    anything is uploaded or persisted — a version with related files persists
    that many Document rows."""

    async def test_single_quota_error_with_one_related_file_and_remaining_one(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """Remaining quota 1, version has 1 related file (2 documents total):
        quota error raised, NOTHING uploaded, NO documents persisted."""
        quota = FakeQuotaService(document_limit=1, documents_used=0)
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            FakeTemplateEngine(),
            quota,
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        with pytest.raises(QuotaExceededError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert doc_files == [], f"expected no uploads, found {doc_files}"
        assert len(fake_document_repo._documents) == 0

    async def test_single_succeeds_when_remaining_quota_covers_all_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """Remaining quota 2 covers primary + 1 related file → succeeds."""
        quota = FakeQuotaService(document_limit=2, documents_used=0)
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            FakeTemplateEngine(),
            quota,
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert len(result["documents"]) == 2
        assert len(fake_document_repo._documents) == 2

    async def test_bulk_quota_error_counts_rows_times_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """rows=2 with 1 related file persists 4 documents: remaining quota 3
        must raise, and nothing may be uploaded or persisted."""
        quota = FakeQuotaService(document_limit=3, documents_used=0)
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            FakeTemplateEngine(),
            quota,
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
        ]
        with pytest.raises(QuotaExceededError):
            await service.generate_bulk(
                template_version_id=version_id,
                rows=rows,
                tenant_id=tenant_id,
                created_by=user_id,
            )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert doc_files == [], f"expected no uploads, found {doc_files}"
        assert len(fake_document_repo._documents) == 0

    async def test_bulk_succeeds_when_remaining_quota_covers_rows_times_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """rows=2 with 1 related file and remaining quota 4 → succeeds with
        4 documents."""
        quota = FakeQuotaService(document_limit=4, documents_used=0)
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            FakeTemplateEngine(),
            quota,
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
        ]
        result = await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert result["document_count"] == 4
        assert len(fake_document_repo._documents) == 4


# ---------------------------------------------------------------------------
# preview — file_id
# ---------------------------------------------------------------------------


class TestPreviewFileId:
    async def test_preview_renders_related_file_bytes(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "app.application.services.document_service.apply_watermark",
            lambda pdf_bytes, text: pdf_bytes,
        )
        engine = RecordingEngine()
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter=FakePdfConverter(convert_result=b"pdf-bytes"),
        )
        version, version_id, _, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )
        file = version.files[0]

        pdf = await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=user_id,
            file_id=str(file.id),
        )

        assert pdf == b"pdf-bytes"
        assert engine.render_calls[-1][0] == b"related-Recibo"

    async def test_preview_unknown_file_id_raises_404(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter=FakePdfConverter(),
        )
        _, version_id, _, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        with pytest.raises(TemplateVersionFileNotFoundError):
            await service.preview(
                template_version_id=version_id,
                variables={"name": "Alice"},
                user_id=user_id,
                file_id=str(uuid.uuid4()),
            )


# ---------------------------------------------------------------------------
# generate_bulk — multi-file
# ---------------------------------------------------------------------------


class TestGenerateBulkMultiFile:
    async def test_rows_times_files_documents_grouped_per_row(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo de pago"]
        )

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
        ]
        result = await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )

        docs = list(fake_document_repo._documents.values())
        assert len(docs) == 4
        assert result["document_count"] == 4

        # One batch for everything
        batch_ids = {d.batch_id for d in docs}
        assert batch_ids == {result["batch_id"]}

        # group_id shared PER ROW: 2 distinct groups, 2 docs each
        group_ids = {d.group_id for d in docs}
        assert len(group_ids) == 2
        assert None not in group_ids
        for gid in group_ids:
            assert sum(1 for d in docs if d.group_id == gid) == 2

        # Naming: label injected before extension, primary naming untouched
        names = sorted(d.docx_file_name for d in docs)
        assert names == [
            "001_Alice.docx",
            "001_Alice_Recibo_de_pago.docx",
            "002_Bob.docx",
            "002_Bob_Recibo_de_pago.docx",
        ]

    async def test_bulk_without_files_keeps_group_id_none(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, engine
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=[]
        )

        rows = [{"name": "Alice", "company": "ACME"}]
        await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )

        docs = list(fake_document_repo._documents.values())
        assert len(docs) == 1
        assert docs[0].group_id is None

    async def test_bulk_rollback_covers_related_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """PDF failure on a related file mid-batch deletes every uploaded
        object of the batch and persists nothing."""
        call_count = 0

        class FailOnFourthCall(FakePdfConverter):
            async def convert(self, docx_bytes: bytes) -> bytes:
                nonlocal call_count
                call_count += 1
                if call_count == 4:
                    raise PdfConversionError("row 2 related file failed")
                return self.convert_result

        engine = FakeTemplateEngine()
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter=FailOnFourthCall(),
        )
        _, version_id, tenant_id, user_id = seed_version_with_files(
            fake_template_repo, fake_storage, labels=["Recibo"]
        )

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
        ]
        with pytest.raises(PdfConversionError):
            await service.generate_bulk(
                template_version_id=version_id,
                rows=rows,
                tenant_id=tenant_id,
                created_by=user_id,
            )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert doc_files == [], f"expected full rollback, found {doc_files}"
        assert len(fake_document_repo._documents) == 0
