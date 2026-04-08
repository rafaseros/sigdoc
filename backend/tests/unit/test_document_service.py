"""Unit tests for DocumentService (task 3.3)."""
import uuid
from datetime import datetime, timezone
from io import BytesIO

import openpyxl
import pytest

from app.application.services.audit_service import AuditService
from app.application.services.document_service import DocumentService
from app.application.services.usage_service import UsageService
from app.domain.entities import AuditAction, Document, Template, TemplateVersion
from app.domain.exceptions import (
    BulkLimitExceededError,
    TemplateAccessDeniedError,
    TemplateVersionNotFoundError,
)
from tests.fakes import (
    FakeAuditRepository,
    FakeDocumentRepository,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
    FakeUsageRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_excel_bytes(headers: list[str], rows: list[list]) -> bytes:
    """Build an in-memory .xlsx with the given headers and data rows."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def make_service(
    fake_doc_repo: FakeDocumentRepository,
    fake_tpl_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    fake_engine: FakeTemplateEngine,
    bulk_limit: int = 10,
    usage_service: UsageService | None = None,
    audit_service: AuditService | None = None,
) -> DocumentService:
    return DocumentService(
        document_repository=fake_doc_repo,
        template_repository=fake_tpl_repo,
        storage=fake_storage,
        engine=fake_engine,
        bulk_generation_limit=bulk_limit,
        usage_service=usage_service,
        audit_service=audit_service,
    )


def seed_version(
    repo: FakeTemplateRepository,
    storage: FakeStorageService,
    variables: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[TemplateVersion, str, str, str]:
    """Seed a template + version in the repo and a template file in storage.

    The Template is seeded so that has_access() returns True for the owner.
    Returns (version, version_id_str, tenant_id_str, user_id_str).
    """
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
    repo._versions[version_id] = version

    # Seed parent template so has_access() works correctly
    template = Template(
        id=template_id,
        tenant_id=tenant_id,
        name="Seeded Template",
        description=None,
        current_version=1,
        created_by=user_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    repo._templates[template_id] = template

    # Seed template bytes in fake storage
    storage.files[("templates", version.minio_path)] = b"fake-docx-bytes"

    return version, str(version_id), str(tenant_id), str(user_id)


# ---------------------------------------------------------------------------
# parse_excel_data — limit enforcement
# ---------------------------------------------------------------------------


class TestParseExcelDataLimitEnforcement:
    async def test_rejects_rows_exceeding_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        limit = 3
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, bulk_limit=limit
        )
        variables = ["col1", "col2"]
        version, version_id, _, _ = seed_version(fake_template_repo, fake_storage, variables)

        # 4 data rows — exceeds limit of 3
        rows = [["val1", "val2"]] * 4
        excel_bytes = make_excel_bytes(variables, rows)

        with pytest.raises(BulkLimitExceededError) as exc_info:
            await service.parse_excel_data(version_id, excel_bytes)

        assert exc_info.value.limit == limit

    async def test_accepts_rows_equal_to_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        limit = 3
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, bulk_limit=limit
        )
        variables = ["col1", "col2"]
        version, version_id, _, _ = seed_version(fake_template_repo, fake_storage, variables)

        # Exactly 3 rows — at limit
        rows = [["val1", "val2"]] * 3
        excel_bytes = make_excel_bytes(variables, rows)

        result = await service.parse_excel_data(version_id, excel_bytes)
        assert len(result) == 3

    async def test_accepts_rows_below_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        limit = 10
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, bulk_limit=limit
        )
        variables = ["name", "email"]
        version, version_id, _, _ = seed_version(fake_template_repo, fake_storage, variables)

        rows = [["Alice", "alice@example.com"], ["Bob", "bob@example.com"]]
        excel_bytes = make_excel_bytes(variables, rows)

        result = await service.parse_excel_data(version_id, excel_bytes)
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[1]["name"] == "Bob"

    async def test_error_carries_configured_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """BulkLimitExceededError.limit must reflect the service's configured limit."""
        limit = 25
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine, bulk_limit=limit
        )
        variables = ["x"]
        version, version_id, _, _ = seed_version(fake_template_repo, fake_storage, variables)

        rows = [["v"]] * (limit + 1)
        excel_bytes = make_excel_bytes(variables, rows)

        with pytest.raises(BulkLimitExceededError) as exc_info:
            await service.parse_excel_data(version_id, excel_bytes)

        assert exc_info.value.limit == limit

    async def test_unknown_version_raises_error(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        unknown_id = str(uuid.uuid4())
        excel_bytes = make_excel_bytes(["col"], [["val"]])

        with pytest.raises(TemplateVersionNotFoundError):
            await service.parse_excel_data(unknown_id, excel_bytes)


# ---------------------------------------------------------------------------
# generate_single
# ---------------------------------------------------------------------------


class TestGenerateSingle:
    async def test_stores_file_in_fake_storage(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        # At least one file should be in the documents bucket
        doc_files = [
            (b, p) for (b, p) in fake_storage.files if b == "documents"
        ]
        assert len(doc_files) >= 1

    async def test_creates_document_record_in_repo(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert len(fake_document_repo._documents) == 1

    async def test_returns_download_url(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Bob", "company": "Corp"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert "download_url" in result
        assert result["download_url"].startswith("http://fake/documents/")

    async def test_document_record_has_correct_fields(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Test", "company": "TestCorp"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        doc = list(fake_document_repo._documents.values())[0]
        assert doc.generation_type == "single"
        assert doc.status == "completed"
        assert doc.template_version_id == uuid.UUID(version_id)
        assert doc.tenant_id == uuid.UUID(tenant_id)


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    async def test_removes_from_repo_and_storage(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, user_id = seed_version(fake_template_repo, fake_storage)

        # Generate a document first
        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        doc = result["document"]
        doc_id = doc.id

        assert len(fake_document_repo._documents) == 1
        # Storage has template file + doc file
        initial_doc_files = [
            (b, p) for (b, p) in fake_storage.files if b == "documents"
        ]
        assert len(initial_doc_files) >= 1

        # Delete
        await service.delete_document(doc_id)

        # Repo should be empty
        assert len(fake_document_repo._documents) == 0

        # No more documents-bucket files
        remaining_doc_files = [
            (b, p) for (b, p) in fake_storage.files if b == "documents"
        ]
        assert len(remaining_doc_files) == 0

    async def test_delete_nonexistent_raises_error(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        from app.domain.exceptions import DocumentNotFoundError

        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        with pytest.raises(DocumentNotFoundError):
            await service.delete_document(uuid.uuid4())


# ---------------------------------------------------------------------------
# Task 5.4: access checks + per-user limits
# ---------------------------------------------------------------------------


class TestGenerateSingleAccessControl:
    """generate_single enforces template access based on ownership and shares."""

    async def test_unrelated_user_is_denied(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """A user who is neither owner nor has a share gets TemplateAccessDeniedError."""
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, _owner_id = seed_version(
            fake_template_repo, fake_storage
        )

        unrelated_user = str(uuid.uuid4())

        with pytest.raises(TemplateAccessDeniedError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Eve", "company": "Evil Corp"},
                tenant_id=tenant_id,
                created_by=unrelated_user,
                role="user",
            )

    async def test_shared_user_can_generate(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """A user with an explicit share record can generate successfully."""
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        owner_id = uuid.uuid4()
        version, version_id, tenant_id, _ = seed_version(
            fake_template_repo, fake_storage, owner_id=owner_id
        )

        shared_user_id = uuid.uuid4()
        template_id = version.template_id

        # Grant the share directly in the fake repo
        await fake_template_repo.add_share(
            template_id=template_id,
            user_id=shared_user_id,
            tenant_id=uuid.UUID(tenant_id),
            shared_by=owner_id,
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Bob", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=str(shared_user_id),
            role="user",
        )

        assert "document" in result
        assert result["document"].created_by == shared_user_id

    async def test_owner_can_generate(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """The template owner can always generate."""
        service = make_service(
            fake_document_repo, fake_template_repo, fake_storage, fake_template_engine
        )
        version, version_id, tenant_id, owner_id = seed_version(
            fake_template_repo, fake_storage
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=owner_id,
            role="user",
        )

        assert "document" in result


class TestPerUserBulkLimit:
    """parse_excel_data enforces per-user limits set in service constructor."""

    async def test_user_with_lower_limit_rejected_at_limit_plus_one(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """User with bulk_generation_limit=5 is rejected at 6 rows."""
        per_user_limit = 5
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            bulk_limit=per_user_limit,
        )
        variables = ["name"]
        version, version_id, _, _ = seed_version(
            fake_template_repo, fake_storage, variables
        )
        excel_bytes = make_excel_bytes(variables, [["Alice"]] * (per_user_limit + 1))

        with pytest.raises(BulkLimitExceededError) as exc_info:
            await service.parse_excel_data(version_id, excel_bytes)

        assert exc_info.value.limit == per_user_limit

    async def test_user_with_lower_limit_accepts_at_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """User with bulk_generation_limit=5 succeeds with exactly 5 rows."""
        per_user_limit = 5
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            bulk_limit=per_user_limit,
        )
        variables = ["name"]
        version, version_id, _, _ = seed_version(
            fake_template_repo, fake_storage, variables
        )
        excel_bytes = make_excel_bytes(variables, [["Alice"]] * per_user_limit)

        result = await service.parse_excel_data(version_id, excel_bytes)
        assert len(result) == per_user_limit

    async def test_global_limit_applies_when_no_per_user_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When the service is built with the global limit, that limit is applied."""
        global_limit = 10
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            bulk_limit=global_limit,
        )
        variables = ["col"]
        version, version_id, _, _ = seed_version(
            fake_template_repo, fake_storage, variables
        )
        # global_limit rows → should succeed
        excel_bytes = make_excel_bytes(variables, [["v"]] * global_limit)
        result = await service.parse_excel_data(version_id, excel_bytes)
        assert len(result) == global_limit

    async def test_global_limit_exceeded_raises_with_correct_limit(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """global_limit + 1 rows raises BulkLimitExceededError(limit=global_limit)."""
        global_limit = 10
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            bulk_limit=global_limit,
        )
        variables = ["col"]
        version, version_id, _, _ = seed_version(
            fake_template_repo, fake_storage, variables
        )
        excel_bytes = make_excel_bytes(variables, [["v"]] * (global_limit + 1))

        with pytest.raises(BulkLimitExceededError) as exc_info:
            await service.parse_excel_data(version_id, excel_bytes)

        assert exc_info.value.limit == global_limit


# ---------------------------------------------------------------------------
# Phase 5 — Usage + Audit integration (tasks 5.1-5.4 RED + GREEN)
# ---------------------------------------------------------------------------


import asyncio as _asyncio


def make_sync_audit_service(repo: FakeAuditRepository) -> AuditService:
    """Return an AuditService backed by FakeAuditRepository.

    Uses the real log() which calls asyncio.create_task(_write(entry)).
    Tests must await asyncio.sleep(0) after calling service methods to allow
    the scheduled task to complete before asserting on the repo state.
    """
    return AuditService(audit_repo=repo)


class TestGenerateSingleWithUsageAndAudit:
    """generate_single() calls usage_service.record() and audit_service.log()."""

    async def test_records_usage_after_generate_single(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_usage_repo: FakeUsageRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        """generate_single records a single-type usage event."""
        usage_svc = UsageService(usage_repo=fake_usage_repo)
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            usage_service=usage_svc,
            audit_service=audit_svc,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert len(fake_usage_repo._events) == 1
        event = fake_usage_repo._events[0]
        assert event.generation_type == "single"
        assert event.document_count == 1

    async def test_logs_audit_after_generate_single(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_usage_repo: FakeUsageRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        """generate_single logs a DOCUMENT_GENERATE audit entry."""
        usage_svc = UsageService(usage_repo=fake_usage_repo)
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            usage_service=usage_svc,
            audit_service=audit_svc,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        entry = fake_audit_repo._entries[0]
        assert entry.action == AuditAction.DOCUMENT_GENERATE

    async def test_generate_single_without_usage_service_does_not_raise(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """generate_single with usage_service=None must not raise."""
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            usage_service=None,
            audit_service=None,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert "document" in result


class TestGenerateBulkWithUsageAndAudit:
    """generate_bulk() calls usage_service.record(type='bulk') and audit_service.log()."""

    async def test_records_bulk_usage_after_generate_bulk(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_usage_repo: FakeUsageRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        """generate_bulk records a bulk-type usage event with correct document_count."""
        usage_svc = UsageService(usage_repo=fake_usage_repo)
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            usage_service=usage_svc,
            audit_service=audit_svc,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

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

        assert len(fake_usage_repo._events) == 1
        event = fake_usage_repo._events[0]
        assert event.generation_type == "bulk"
        assert event.document_count == 3

    async def test_logs_audit_after_generate_bulk(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_usage_repo: FakeUsageRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        """generate_bulk logs a DOCUMENT_GENERATE_BULK audit entry."""
        usage_svc = UsageService(usage_repo=fake_usage_repo)
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            usage_service=usage_svc,
            audit_service=audit_svc,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        rows = [{"name": "Alice", "company": "ACME"}]
        await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=user_id,
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.DOCUMENT_GENERATE_BULK


class TestDeleteDocumentAudit:
    """delete_document() calls audit_service.log(DOCUMENT_DELETE)."""

    async def test_logs_audit_on_delete(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """delete_document logs a DOCUMENT_DELETE audit entry."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            audit_service=audit_svc,
        )
        version, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )
        doc_id = result["document"].id

        # Clear audit entries from generate_single (fire-and-forget — drain first)
        await _asyncio.sleep(0)
        fake_audit_repo._entries.clear()

        await service.delete_document(doc_id)
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.DOCUMENT_DELETE


# ---------------------------------------------------------------------------
# Task 7.2 — Quota integration with DocumentService
# ---------------------------------------------------------------------------


from app.domain.entities.subscription_tier import FREE_TIER_ID  # noqa: E402
from tests.fakes import FakeQuotaService  # noqa: E402


def make_service_with_quota(
    fake_doc_repo: FakeDocumentRepository,
    fake_tpl_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    fake_engine: FakeTemplateEngine,
    fake_quota_svc: FakeQuotaService,
) -> DocumentService:
    """DocumentService wired with a FakeQuotaService and FREE_TIER_ID."""
    return DocumentService(
        document_repository=fake_doc_repo,
        template_repository=fake_tpl_repo,
        storage=fake_storage,
        engine=fake_engine,
        bulk_generation_limit=10,
        quota_service=fake_quota_svc,
        tier_id=FREE_TIER_ID,
    )


class TestGenerateSingleWithQuota:
    """generate_single() propagates QuotaExceededError from quota_service."""

    async def test_quota_exceeded_propagates(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When quota_service raises, generate_single propagates QuotaExceededError."""
        from app.domain.exceptions import QuotaExceededError

        quota_svc = FakeQuotaService(exceeded_resource="monthly_document_limit")
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            quota_svc,
        )
        _, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        with pytest.raises(QuotaExceededError) as exc_info:
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )

        assert exc_info.value.limit_type == "monthly_document_limit"

    async def test_no_document_created_when_quota_exceeded(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When quota raises, no document record is created."""
        quota_svc = FakeQuotaService(exceeded_resource="monthly_document_limit")
        service = make_service_with_quota(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            quota_svc,
        )
        _, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        try:
            await service.generate_single(
                template_version_id=version_id,
                variables={"name": "Alice", "company": "ACME"},
                tenant_id=tenant_id,
                created_by=user_id,
            )
        except Exception:
            pass

        assert len(fake_document_repo._documents) == 0

    async def test_quota_service_none_is_backward_compat(
        self,
        fake_document_repo: FakeDocumentRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """quota_service=None → no quota check, generation succeeds as before."""
        service = make_service(
            fake_document_repo,
            fake_template_repo,
            fake_storage,
            fake_template_engine,
        )
        _, version_id, tenant_id, user_id = seed_version(
            fake_template_repo, fake_storage
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice", "company": "ACME"},
            tenant_id=tenant_id,
            created_by=user_id,
        )

        assert "document" in result
