"""Unit tests for PDF-related DocumentService methods — Phase 3.

Covers T-APP-01 (atomic dual-format single generate),
T-APP-03 (atomic bulk dual-format with rollback),
T-APP-05 (ensure_pdf lazy backfill).

All tests use FakePdfConverter + FakeStorageService + FakeDocumentRepository
so they run without Gotenberg, MinIO, or DB.

Strict TDD order: test file written first (RED), then DocumentService
implementation updated (GREEN).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.document_service import DocumentService
from app.domain.entities import AuditAction, Document, Template, TemplateVersion
from app.domain.exceptions import PdfConversionError
from tests.fakes import (
    FakeAuditRepository,
    FakeDocumentRepository,
    FakePdfConverter,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    doc_repo: FakeDocumentRepository,
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
    pdf_converter: FakePdfConverter,
    audit_service: AuditService | None = None,
) -> DocumentService:
    """Build a DocumentService with FakePdfConverter wired in."""
    return DocumentService(
        document_repository=doc_repo,
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
        pdf_converter=pdf_converter,
        audit_service=audit_service,
    )


def seed_version(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    variables: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[TemplateVersion, str, str, str]:
    """Seed a template + version + template bytes. Returns (version, version_id_str, tenant_id_str, user_id_str)."""
    if variables is None:
        variables = ["name", "company"]

    tenant_id = uuid.uuid4()
    user_id = owner_id if owner_id is not None else uuid.uuid4()
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
        name="Test Template",
        description=None,
        current_version=1,
        created_by=user_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    tpl_repo._templates[template_id] = template

    storage.files[("templates", version.minio_path)] = b"fake-docx-bytes"
    return version, str(version_id), str(tenant_id), str(user_id)


def seed_legacy_document(
    doc_repo: FakeDocumentRepository,
    storage: FakeStorageService,
    tenant_id: str,
    user_id: str,
    version_id: str,
) -> Document:
    """Seed a legacy Document row (pdf_file_name=None) and its DOCX in storage."""
    doc_id = uuid.uuid4()
    docx_file_name = "legacy_doc.docx"
    docx_minio_path = f"{tenant_id}/{doc_id}/{docx_file_name}"

    doc = Document(
        id=doc_id,
        tenant_id=uuid.UUID(tenant_id),
        template_version_id=uuid.UUID(version_id),
        docx_file_name=docx_file_name,
        docx_minio_path=docx_minio_path,
        generation_type="single",
        variables_snapshot={},
        created_by=uuid.UUID(user_id),
        pdf_file_name=None,  # legacy: no PDF yet
        pdf_minio_path=None,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    doc_repo._documents[doc_id] = doc

    # Seed the DOCX in storage so ensure_pdf can download it
    storage.files[("documents", docx_minio_path)] = b"legacy-docx-bytes"

    return doc


# ---------------------------------------------------------------------------
# Group B — T-APP-01: Atomic dual-format single generate
# ---------------------------------------------------------------------------


class TestGenerateSingleDualFormat:
    """generate_single produces DOCX + PDF, persists both; rolls back DOCX on converter failure."""

    # ── SCEN-DDF-01 / REQ-DDF-03 ────────────────────────────────────────────

    async def test_happy_path_uploads_both_files_to_storage(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Both DOCX and PDF objects land in the documents bucket on success."""
        pdf_converter = FakePdfConverter()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        doc_files = [p for (b, p) in fake_storage.files if b == "documents"]
        docx_files = [p for p in doc_files if p.endswith(".docx")]
        pdf_files = [p for p in doc_files if p.endswith(".pdf")]

        assert len(docx_files) == 1, "Expected exactly one DOCX in documents bucket"
        assert len(pdf_files) == 1, "Expected exactly one PDF in documents bucket"

    async def test_happy_path_document_row_has_both_file_fields(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """The persisted Document entity has both docx_* and pdf_* fields populated."""
        pdf_converter = FakePdfConverter()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert len(fake_document_repo._documents) == 1
        doc = list(fake_document_repo._documents.values())[0]

        assert doc.docx_file_name is not None and doc.docx_file_name.endswith(".docx")
        assert doc.docx_minio_path is not None
        assert doc.pdf_file_name is not None and doc.pdf_file_name.endswith(".pdf")
        assert doc.pdf_minio_path is not None

    # ── SCEN-DDF-05 / REQ-DDF-05 ────────────────────────────────────────────

    async def test_pdf_failure_deletes_uploaded_docx(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When PdfConverter fails, the already-uploaded DOCX is deleted from MinIO."""
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unavailable"))
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        with pytest.raises(PdfConversionError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )

        # No documents-bucket files should remain
        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert len(doc_files) == 0, (
            "DOCX should have been deleted after PdfConversionError"
        )

    async def test_pdf_failure_no_db_row(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When PdfConverter fails, no Document row is persisted."""
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unavailable"))
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        with pytest.raises(PdfConversionError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )

        assert len(fake_document_repo._documents) == 0

    # ── REQ-DDF-14: formats_generated in audit log ────────────────────────────

    async def test_audit_log_contains_formats_generated(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """Audit event for DOCUMENT_GENERATE includes details.formats_generated=["docx","pdf"]."""
        pdf_converter = FakePdfConverter()
        audit_svc = AuditService(audit_repo=fake_audit_repo)
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine,
            pdf_converter, audit_service=audit_svc,
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )
        # Flush fire-and-forget audit task
        await asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        entry = fake_audit_repo._entries[0]
        assert entry.action == AuditAction.DOCUMENT_GENERATE
        assert entry.details is not None
        assert entry.details.get("formats_generated") == ["docx", "pdf"], (
            f"Expected formats_generated=['docx','pdf'], got {entry.details}"
        )

    # ── REQ-DDF-16: quota incremented by exactly 1 ───────────────────────────

    async def test_quota_incremented_by_exactly_one(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Quota counter is incremented by exactly 1, even though two files are generated."""
        from app.domain.entities.subscription_tier import FREE_TIER_ID
        from tests.fakes import FakeQuotaService

        quota_calls: list[int] = []

        class TrackingQuotaService(FakeQuotaService):
            async def check_document_quota(self, tenant_id, tier_id, additional):
                quota_calls.append(additional)
                await super().check_document_quota(
                    tenant_id=tenant_id, tier_id=tier_id, additional=additional
                )

        pdf_converter = FakePdfConverter()
        quota_svc = TrackingQuotaService()
        service = DocumentService(
            document_repository=fake_document_repo,
            template_repository=fake_template_repo,
            storage=fake_storage,
            engine=fake_template_engine,
            pdf_converter=pdf_converter,
            quota_service=quota_svc,
            tier_id=FREE_TIER_ID,
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert quota_calls == [1], (
            f"Expected quota incremented by exactly 1, got calls: {quota_calls}"
        )


# ---------------------------------------------------------------------------
# Group C — T-APP-03: Atomic bulk dual-format with rollback
# ---------------------------------------------------------------------------


class TestGenerateBulkDualFormat:
    """generate_bulk atomic: all docs get DOCX+PDF; on any row failure, all uploaded files deleted."""

    async def test_happy_path_all_rows_get_both_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Successful bulk: every row produces both DOCX and PDF in storage, all rows persisted."""
        pdf_converter = FakePdfConverter()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
            {"name": "Carol", "company": "Ltd"},
        ]
        await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        docx_files = [p for (_, p) in doc_files if p.endswith(".docx")]
        pdf_files = [p for (_, p) in doc_files if p.endswith(".pdf")]

        assert len(docx_files) == 3
        assert len(pdf_files) == 3
        assert len(fake_document_repo._documents) == 3

    async def test_bulk_row_failure_deletes_all_uploaded_files(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When row 3 fails, DOCX files from rows 1 and 2 are deleted from MinIO."""
        call_count = 0

        class FailOnThirdCall(FakePdfConverter):
            async def convert(self, docx_bytes: bytes) -> bytes:
                nonlocal call_count
                call_count += 1
                if call_count == 3:
                    raise PdfConversionError("Row 3 conversion failed")
                return self.convert_result

        pdf_converter = FailOnThirdCall()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
            {"name": "Carol", "company": "Ltd"},
            {"name": "Dave", "company": "Inc"},
            {"name": "Eve", "company": "Evil"},
        ]

        with pytest.raises(PdfConversionError):
            await service.generate_bulk(
                template_version_id=version_id,
                rows=rows,
                tenant_id=tenant_id,
                created_by=user_id,
            )

        # All documents-bucket files should be deleted (rows 1 and 2 had DOCX+PDF uploaded)
        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert len(doc_files) == 0, (
            f"Expected all bulk files deleted after rollback, but found: {[p for (_, p) in doc_files]}"
        )

    async def test_bulk_row_failure_no_db_rows_persisted(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When bulk fails, no Document rows are written to the DB."""
        call_count = 0

        class FailOnSecondCall(FakePdfConverter):
            async def convert(self, docx_bytes: bytes) -> bytes:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise PdfConversionError("Row 2 conversion failed")
                return self.convert_result

        pdf_converter = FailOnSecondCall()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        rows = [
            {"name": "Alice", "company": "ACME"},
            {"name": "Bob", "company": "Corp"},
            {"name": "Carol", "company": "Ltd"},
        ]

        with pytest.raises(PdfConversionError):
            await service.generate_bulk(
                template_version_id=version_id,
                rows=rows,
                tenant_id=tenant_id,
                created_by=user_id,
            )

        assert len(fake_document_repo._documents) == 0

    async def test_bulk_audit_log_contains_formats_generated(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """Bulk audit event includes details.formats_generated=["docx","pdf"]."""
        pdf_converter = FakePdfConverter()
        audit_svc = AuditService(audit_repo=fake_audit_repo)
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine,
            pdf_converter, audit_service=audit_svc,
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        rows = [{"name": "Alice", "company": "ACME"}]
        await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        await asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        entry = fake_audit_repo._entries[0]
        assert entry.action == AuditAction.DOCUMENT_GENERATE_BULK
        assert entry.details is not None
        assert entry.details.get("formats_generated") == ["docx", "pdf"]


# ---------------------------------------------------------------------------
# Group D — T-APP-05: ensure_pdf lazy backfill
# ---------------------------------------------------------------------------


class TestEnsurePdf:
    """ensure_pdf(document_id) lazy-backfills PDF for legacy docs, is idempotent, propagates failures."""

    # ── SCEN-DDF-06 / REQ-DDF-09 ─────────────────────────────────────────────

    async def test_legacy_doc_backfill_happy_path_returns_updated_doc(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """ensure_pdf on a legacy doc returns the updated Document with pdf fields set."""
        pdf_converter = FakePdfConverter(convert_result=b"generated-pdf-bytes")
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        result = await service.ensure_pdf(legacy_doc.id)

        assert result.pdf_file_name is not None and result.pdf_file_name.endswith(".pdf")
        assert result.pdf_minio_path is not None

    async def test_legacy_doc_backfill_uploads_pdf_to_storage(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """ensure_pdf uploads the generated PDF to the documents bucket."""
        pdf_converter = FakePdfConverter(convert_result=b"generated-pdf-bytes")
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        await service.ensure_pdf(legacy_doc.id)

        pdf_files = [p for (b, p) in fake_storage.files if b == "documents" and p.endswith(".pdf")]
        assert len(pdf_files) == 1

    async def test_legacy_doc_backfill_calls_update_pdf_fields(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """ensure_pdf calls update_pdf_fields on the document repository."""
        pdf_converter = FakePdfConverter()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        await service.ensure_pdf(legacy_doc.id)

        # After ensure_pdf, the document in repo should have pdf fields set
        updated = fake_document_repo._documents[legacy_doc.id]
        assert updated.pdf_file_name is not None
        assert updated.pdf_minio_path is not None

    # ── Idempotency ────────────────────────────────────────────────────────────

    async def test_idempotent_already_has_pdf_skips_conversion(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """ensure_pdf on a doc that already has pdf_file_name returns immediately, no conversion."""
        pdf_converter = FakePdfConverter()
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        # Seed a doc with PDF already set
        doc_id = uuid.uuid4()
        doc = Document(
            id=doc_id,
            tenant_id=uuid.UUID(tenant_id),
            template_version_id=uuid.UUID(version_id),
            docx_file_name="doc.docx",
            docx_minio_path=f"{tenant_id}/{doc_id}/doc.docx",
            generation_type="single",
            variables_snapshot={},
            created_by=uuid.UUID(user_id),
            pdf_file_name="doc.pdf",
            pdf_minio_path=f"{tenant_id}/{doc_id}/doc.pdf",
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        fake_document_repo._documents[doc_id] = doc

        result = await service.ensure_pdf(doc_id)

        # Converter should NOT have been called
        assert pdf_converter.call_count == 0
        # Should return the same pdf_minio_path
        assert result.pdf_minio_path == doc.pdf_minio_path

    # ── SCEN-DDF-07 / REQ-DDF-10 ─────────────────────────────────────────────

    async def test_backfill_failure_raises_pdf_conversion_error(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """ensure_pdf propagates PdfConversionError when converter fails."""
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unreachable"))
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        with pytest.raises(PdfConversionError):
            await service.ensure_pdf(legacy_doc.id)

    async def test_backfill_failure_does_not_update_db_row(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """On converter failure, pdf_file_name remains NULL — no partial write."""
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unreachable"))
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        with pytest.raises(PdfConversionError):
            await service.ensure_pdf(legacy_doc.id)

        # Document row must remain unmodified
        stored = fake_document_repo._documents[legacy_doc.id]
        assert stored.pdf_file_name is None, (
            "pdf_file_name must remain NULL after converter failure"
        )

    async def test_backfill_failure_does_not_delete_docx(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """On backfill converter failure, the DOCX in MinIO is NOT deleted (REQ-DDF-10)."""
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unreachable"))
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, pdf_converter
        )
        _, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)
        legacy_doc = seed_legacy_document(
            fake_document_repo, fake_storage, tenant_id, user_id, version_id
        )

        with pytest.raises(PdfConversionError):
            await service.ensure_pdf(legacy_doc.id)

        # DOCX must still be in storage
        assert ("documents", legacy_doc.docx_minio_path) in fake_storage.files, (
            "DOCX must NOT be deleted during backfill failure (REQ-DDF-10)"
        )
