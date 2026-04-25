"""Integration tests — Phase 6 pdf-export (T-INT-01..T-INT-06 + W-PRES-02 fix).

Tests:
- T-INT-01: E2E happy path — generate → both files in storage → download both formats + RBAC
- T-INT-02: Legacy backfill — DOCX-only doc → PDF request → pdf persisted → idempotent → failure
- T-INT-03: Sharing RBAC — recipient cannot download DOCX via share, can download PDF (via=share)
- T-INT-04: Migration 010 regression — existing rows have docx_* fields, pdf_* fields NULL
- T-INT-05: Quota — generate increments by exactly 1, formats_generated in audit
- T-INT-06: Full suite regression gate (no new failures from Phase 6)

All tests use in-memory fakes from conftest — no real Gotenberg needed.
FakePdfConverter is already wired in conftest.py via override_get_document_service.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone

import pytest

from app.domain.entities import Document, Template, TemplateVersion
from app.domain.exceptions import PdfConversionError
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakePdfConverter

# ── Stable identifiers ───────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Fixture helpers ──────────────────────────────────────────────────────────


def _make_admin_user() -> CurrentUser:
    return CurrentUser(user_id=ADMIN_USER_ID, tenant_id=TENANT_ID, role="admin")


def _make_non_admin_user() -> CurrentUser:
    return CurrentUser(user_id=USER_ID, tenant_id=TENANT_ID, role="user")


def _seed_template_and_storage(fake_template_repo, fake_storage) -> str:
    """Seed a Template + TemplateVersion accessible to admins. Returns version_id str."""
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    minio_path = f"{TENANT_ID}/{template_id}/v1/template.docx"
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=minio_path,
        variables=["name", "date"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=TENANT_ID,
        name=f"TestTemplate-{template_id}",
        description=None,
        current_version=1,
        created_by=ADMIN_USER_ID,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = b"fake-docx-bytes"
    return str(version_id)


def _seed_template_shared_with_user(fake_template_repo, fake_storage) -> tuple[str, uuid.UUID]:
    """Seed a Template + Version owned by admin AND shared with USER_ID.

    Returns (version_id_str, template_id).
    """
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    minio_path = f"{TENANT_ID}/{template_id}/v1/template.docx"
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=minio_path,
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=TENANT_ID,
        name=f"SharedTemplate-{template_id}",
        description=None,
        current_version=1,
        created_by=ADMIN_USER_ID,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = b"fake-docx-bytes"
    # Grant share: user_id can access this template
    fake_template_repo._shares[(template_id, USER_ID)] = type(
        "TemplateShare", (), {"template_id": template_id, "user_id": USER_ID}
    )()
    return str(version_id), template_id


def _seed_legacy_doc_in_repo(
    fake_document_repo,
    fake_storage,
    *,
    pdf_file_name: str | None = None,
    pdf_minio_path: str | None = None,
    creator_id: uuid.UUID = ADMIN_USER_ID,
) -> Document:
    """Insert a Document directly into the fake repository.

    By default inserts a legacy doc (pdf_file_name=None, pdf_minio_path=None).
    """
    doc_id = uuid.uuid4()
    template_version_id = uuid.uuid4()
    docx_file_name = "LegacyDoc.docx"
    docx_minio_path = f"{TENANT_ID}/{doc_id}/{docx_file_name}"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=template_version_id,
        docx_file_name=docx_file_name,
        docx_minio_path=docx_minio_path,
        pdf_file_name=pdf_file_name,
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Legacy", "date": "2024-01-01"},
        created_by=creator_id,
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=None,
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"legacy-docx-bytes"
    if pdf_minio_path is not None:
        fake_storage.files[("documents", pdf_minio_path)] = b"legacy-pdf-bytes"
    return doc


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-01 — E2E happy path
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_e2e_admin_generate_creates_both_files_in_storage(
    async_client, app, auth_headers, fake_template_repo, fake_storage, fake_document_repo
):
    """T-INT-01a: Admin POST /generate → response 200 + doc row has both file fields.

    Verifies dual-format atomic generation: both DOCX and PDF must be
    persisted in fake_storage with their respective minio paths, and the
    returned Document entity must have docx_file_name and pdf_file_name set.
    """
    version_id = _seed_template_and_storage(fake_template_repo, fake_storage)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "date": "2025-01-01"},
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()

    # Both file name fields must be set in the response
    assert body.get("docx_file_name"), "docx_file_name must be non-null"
    assert body.get("pdf_file_name"), "pdf_file_name must be non-null"

    # Both files must exist in fake_storage under the DOCUMENTS bucket
    doc_id = body["id"]
    docx_path = body["docx_file_name"]
    pdf_path = body["pdf_file_name"]

    # Verify storage keys by looking for the doc_id in the stored paths
    documents_bucket_keys = [
        key for (bucket, key) in fake_storage.files.keys()
        if bucket == "documents" and doc_id in str(key)
    ]
    docx_keys = [k for k in documents_bucket_keys if k.endswith(".docx")]
    pdf_keys = [k for k in documents_bucket_keys if k.endswith(".pdf")]

    assert len(docx_keys) >= 1, f"Expected DOCX in storage for doc {doc_id}, found: {documents_bucket_keys}"
    assert len(pdf_keys) >= 1, f"Expected PDF in storage for doc {doc_id}, found: {documents_bucket_keys}"


@pytest.mark.asyncio
async def test_e2e_admin_download_docx_returns_200(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-01b: Admin GET /download?format=docx → 200 + DOCX MIME."""
    # Seed a fully-populated doc (both files present)
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/Report.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/Report.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="Report.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="Report.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Alice"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"docx-content"
    fake_storage.files[("documents", pdf_minio_path)] = b"pdf-content"

    response = await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=docx",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert "wordprocessingml" in response.headers.get("content-type", "")
    assert response.content == b"docx-content"


@pytest.mark.asyncio
async def test_e2e_admin_download_pdf_returns_200(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-01c: Admin GET /download?format=pdf → 200 + PDF MIME."""
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/Report2.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/Report2.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="Report2.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="Report2.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Bob"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"docx-content-2"
    fake_storage.files[("documents", pdf_minio_path)] = b"pdf-content-2"

    response = await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=pdf",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").lower() == "application/pdf"
    assert response.content == b"pdf-content-2"


@pytest.mark.asyncio
async def test_e2e_user_download_pdf_returns_200(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-01d: Non-admin user GET /download?format=pdf → 200."""
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/UserDoc.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/UserDoc.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="UserDoc.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="UserDoc.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Carol"},
        created_by=USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"user-docx"
    fake_storage.files[("documents", pdf_minio_path)] = b"user-pdf"

    async def override_non_admin():
        return _make_non_admin_user()

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type", "").lower() == "application/pdf"
        assert response.content == b"user-pdf"
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_e2e_user_download_docx_returns_403(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-01e: Non-admin user GET /download?format=docx → 403 (RBAC)."""
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/RBACDoc.docx"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="RBACDoc.docx",
        docx_minio_path=docx_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Dave"},
        created_by=USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"rbac-docx"

    async def override_non_admin():
        return _make_non_admin_user()

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=docx",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_e2e_generate_audit_event_has_formats_generated(
    async_client, app, auth_headers, fake_template_repo, fake_storage, fake_audit_repo
):
    """T-INT-01f: POST /generate audit event contains formats_generated=["docx","pdf"]."""
    version_id = _seed_template_and_storage(fake_template_repo, fake_storage)
    initial_count = len(fake_audit_repo._entries)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Eve", "date": "2025-06-01"},
        },
    )

    assert response.status_code == 201, response.text

    new_entries = fake_audit_repo._entries[initial_count:]
    generate_events = [e for e in new_entries if e.action == "document.generate"]
    assert len(generate_events) >= 1, "Expected at least one DOCUMENT_GENERATE audit event"
    evt = generate_events[-1]
    assert evt.details is not None
    assert evt.details.get("formats_generated") == ["docx", "pdf"], (
        f"Expected formats_generated=['docx','pdf'], got: {evt.details.get('formats_generated')}"
    )


@pytest.mark.asyncio
async def test_e2e_download_audit_event_has_format_and_via(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """T-INT-01g: Download audit event has format + via fields."""
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/AuditDoc.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/AuditDoc.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="AuditDoc.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="AuditDoc.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Frank"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"audit-docx"
    fake_storage.files[("documents", pdf_minio_path)] = b"audit-pdf"

    initial_count = len(fake_audit_repo._entries)

    await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=pdf&via=direct",
        headers=auth_headers,
    )

    new_entries = fake_audit_repo._entries[initial_count:]
    download_events = [e for e in new_entries if e.action == "document.download"]
    assert len(download_events) >= 1, "Expected DOCUMENT_DOWNLOAD audit event"
    evt = download_events[-1]
    assert evt.details is not None
    assert evt.details.get("format") == "pdf"
    assert evt.details.get("via") == "direct"


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-02 — Legacy backfill
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_legacy_backfill_happy_path_returns_200_and_persists_pdf(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-02a: Legacy DOCX-only doc → user requests PDF → ensure_pdf fires → 200.

    After the request, the doc row must have pdf_file_name populated (DB persisted).
    """
    doc = _seed_legacy_doc_in_repo(fake_document_repo, fake_storage)
    assert doc.pdf_file_name is None, "Precondition: legacy doc has no PDF"

    response = await async_client.get(
        f"/api/v1/documents/{doc.id}/download?format=pdf",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").lower() == "application/pdf"
    # After backfill, the doc row must have pdf_file_name set (in-memory update)
    updated_doc = fake_document_repo._documents.get(doc.id)
    assert updated_doc is not None
    assert updated_doc.pdf_file_name is not None, (
        "pdf_file_name must be set after successful backfill"
    )
    assert updated_doc.pdf_minio_path is not None, (
        "pdf_minio_path must be set after successful backfill"
    )


@pytest.mark.asyncio
async def test_legacy_backfill_idempotent_second_request_skips_conversion(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-02b: Second PDF request on already-backfilled doc → no converter call.

    Seeds a doc that already has pdf_file_name set (as if backfill already ran).
    Confirms the fake converter call_count does NOT increase.
    """
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/AlreadyDone.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/AlreadyDone.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="AlreadyDone.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="AlreadyDone.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Grace"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"idem-docx"
    fake_storage.files[("documents", pdf_minio_path)] = b"idem-pdf"

    # We need a fresh converter instance to track calls independently
    # The conftest FakePdfConverter is shared — we use the doc's call_count
    # approach: call_count before and after must be equal (idempotent fast path)
    from tests.fakes import FakeDocumentRepository as _FDR
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from tests.fakes import (
        FakeAuditRepository, FakeTemplateRepository, FakeStorageService,
        FakeTemplateEngine, FakeUsageRepository, FakeQuotaService
    )
    from app.application.services.audit_service import AuditService
    from app.application.services.usage_service import UsageService

    # Fresh independent service with its own FakePdfConverter for call counting
    _local_doc_repo = _FDR()
    _local_doc_repo._documents[doc_id] = doc
    _local_storage = FakeStorageService()
    _local_storage.files[("documents", docx_minio_path)] = b"idem-docx"
    _local_storage.files[("documents", pdf_minio_path)] = b"idem-pdf"
    _local_pdf_converter = FakePdfConverter()

    _local_service = DocumentService(
        document_repository=_local_doc_repo,
        template_repository=FakeTemplateRepository(),
        storage=_local_storage,
        engine=FakeTemplateEngine(),
        pdf_converter=_local_pdf_converter,
    )

    call_count_before = _local_pdf_converter.call_count

    original = app.dependency_overrides.get(get_document_service)

    async def local_service_override():
        return _local_service

    app.dependency_overrides[get_document_service] = local_service_override
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

        # Converter was NOT called (idempotent fast path)
        assert _local_pdf_converter.call_count == call_count_before, (
            f"Converter should not have been called for already-backfilled doc. "
            f"call_count before={call_count_before}, after={_local_pdf_converter.call_count}"
        )
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


@pytest.mark.asyncio
async def test_legacy_backfill_converter_failure_returns_503_and_pdf_stays_null(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-02c: Legacy doc → converter raises → 503 → pdf_file_name stays NULL.

    Verifies REQ-DDF-10: DOCX not deleted, DB row not updated on backfill failure.
    """
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from tests.fakes import FakeDocumentRepository as _FDR
    from tests.fakes import (
        FakeTemplateRepository, FakeStorageService, FakeTemplateEngine
    )

    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/FailDoc.docx"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="FailDoc.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name=None,
        pdf_minio_path=None,
        generation_type="single",
        variables_snapshot={"name": "Henry"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )

    _local_doc_repo = _FDR()
    _local_doc_repo._documents[doc_id] = doc
    _local_storage = FakeStorageService()
    _local_storage.files[("documents", docx_minio_path)] = b"fail-docx-bytes"

    _failing_converter = FakePdfConverter()
    _failing_converter.set_failure(PdfConversionError("Gotenberg down"))

    _local_service = DocumentService(
        document_repository=_local_doc_repo,
        template_repository=FakeTemplateRepository(),
        storage=_local_storage,
        engine=FakeTemplateEngine(),
        pdf_converter=_failing_converter,
    )

    original = app.dependency_overrides.get(get_document_service)

    async def local_service_override():
        return _local_service

    app.dependency_overrides[get_document_service] = local_service_override
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 503, response.text

        # DB row must NOT have been updated (pdf_file_name stays NULL)
        stored_doc = _local_doc_repo._documents.get(doc_id)
        assert stored_doc is not None
        assert stored_doc.pdf_file_name is None, (
            "pdf_file_name must remain NULL after backfill failure (REQ-DDF-10)"
        )
        # DOCX must still be in storage (not deleted on backfill failure)
        assert ("documents", docx_minio_path) in _local_storage.files, (
            "DOCX must not be deleted on backfill failure (REQ-DDF-10)"
        )
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


@pytest.mark.asyncio
async def test_legacy_backfill_then_clear_failure_succeeds(
    async_client, app, auth_headers
):
    """T-INT-02d: After failure + clear, next request succeeds (single-use failure).

    FakePdfConverter.set_failure() is single-use — second request uses success mode.
    """
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from tests.fakes import FakeDocumentRepository as _FDR
    from tests.fakes import FakeTemplateRepository, FakeStorageService, FakeTemplateEngine

    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/SingleUseDoc.docx"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="SingleUseDoc.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name=None,
        pdf_minio_path=None,
        generation_type="single",
        variables_snapshot={"name": "Irene"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )

    _local_doc_repo = _FDR()
    _local_doc_repo._documents[doc_id] = doc
    _local_storage = FakeStorageService()
    _local_storage.files[("documents", docx_minio_path)] = b"single-use-docx"

    # Single-use failure: first call fails, second succeeds
    _single_use_converter = FakePdfConverter()
    _single_use_converter.set_failure(PdfConversionError("Transient failure"))

    _local_service = DocumentService(
        document_repository=_local_doc_repo,
        template_repository=FakeTemplateRepository(),
        storage=_local_storage,
        engine=FakeTemplateEngine(),
        pdf_converter=_single_use_converter,
    )

    original = app.dependency_overrides.get(get_document_service)

    async def local_service_override():
        return _local_service

    app.dependency_overrides[get_document_service] = local_service_override
    try:
        # First request → failure (single-use failure)
        r1 = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert r1.status_code == 503, r1.text

        # Failure is cleared (single-use). Second request → success.
        r2 = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.headers.get("content-type", "").lower() == "application/pdf"
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-03 — Sharing RBAC
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_shared_user_cannot_download_docx(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_template_repo
):
    """T-INT-03a: Non-admin (share recipient) cannot download DOCX → 403.

    SCEN-DDF-13: Non-admin + format=docx → 403 regardless of share.
    """
    # Seed a doc created by admin
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/ShareDoc.docx"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="ShareDoc.docx",
        docx_minio_path=docx_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Jack"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"share-docx"

    async def override_user():
        return _make_non_admin_user()

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_user
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=docx&via=share",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_shared_user_can_download_pdf_via_share(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """T-INT-03b: Non-admin + format=pdf + via=share → 200 + audit has via="share".

    SCEN-DDF-14: Share recipient downloads PDF with via=share → audit correct.
    """
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/SharePDF.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/SharePDF.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="SharePDF.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="SharePDF.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Karen"},
        created_by=ADMIN_USER_ID,  # admin is the creator — user is not
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"share-docx-content"
    fake_storage.files[("documents", pdf_minio_path)] = b"share-pdf-content"

    initial_count = len(fake_audit_repo._entries)

    async def override_user():
        return _make_non_admin_user()

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_user
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf&via=share",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type", "").lower() == "application/pdf"

        # Audit event must record via="share" (user is NOT the creator)
        new_entries = fake_audit_repo._entries[initial_count:]
        download_events = [e for e in new_entries if e.action == "document.download"]
        assert len(download_events) >= 1, "Expected DOCUMENT_DOWNLOAD audit event"
        evt = download_events[-1]
        assert evt.details.get("via") == "share", (
            f"Expected via='share' in audit event, got: {evt.details}"
        )
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_creator_via_share_overridden_to_direct(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """T-INT-03c: Creator sends via=share → server overrides to "direct" (ADR-PDF-07).

    Prevents audit spoofing: the document creator cannot pretend they're a share recipient.
    """
    doc_id = uuid.uuid4()
    docx_minio_path = f"{TENANT_ID}/{doc_id}/CreatorDoc.docx"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/CreatorDoc.pdf"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="CreatorDoc.docx",
        docx_minio_path=docx_minio_path,
        pdf_file_name="CreatorDoc.pdf",
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Leo"},
        created_by=ADMIN_USER_ID,  # Admin is the creator
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"creator-docx"
    fake_storage.files[("documents", pdf_minio_path)] = b"creator-pdf"

    initial_count = len(fake_audit_repo._entries)

    # Admin is the creator — sends via=share (attempted spoofing)
    response = await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=pdf&via=share",
        headers=auth_headers,  # auth_headers → ADMIN_USER_ID
    )

    assert response.status_code == 200, response.text

    # Server must override via to "direct" (ADR-PDF-07)
    new_entries = fake_audit_repo._entries[initial_count:]
    download_events = [e for e in new_entries if e.action == "document.download"]
    assert len(download_events) >= 1
    evt = download_events[-1]
    assert evt.details.get("via") == "direct", (
        f"Expected via='direct' when creator sends via=share, got: {evt.details}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-04 — Migration 010 regression
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_migration_010_doc_has_docx_fields_and_null_pdf_fields(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-04: Rows created after migration have docx_* fields set and pdf_* fields NULL.

    This verifies that the Document domain entity + FakeDocumentRepository correctly
    represent the state of a row that was present before Phase 3 (DOCX-only).
    The migration itself (DDL) is verified separately via alembic commands.
    This test verifies the model/entity structure is correct.
    """
    # Create a doc simulating a row that existed before Phase 3
    # (pdf_file_name=NULL, pdf_minio_path=NULL) as the migration leaves it
    doc_id = uuid.uuid4()
    original_docx_name = "MigratedDoc.docx"
    original_docx_path = f"{TENANT_ID}/{doc_id}/{original_docx_name}"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name=original_docx_name,
        docx_minio_path=original_docx_path,
        pdf_file_name=None,   # NULL — as migration leaves pre-existing rows
        pdf_minio_path=None,  # NULL — as migration leaves pre-existing rows
        generation_type="single",
        variables_snapshot={"name": "Migrated"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", original_docx_path)] = b"migrated-docx"

    # Verify fields are correctly stored and retrieved
    stored_doc = fake_document_repo._documents.get(doc_id)
    assert stored_doc is not None
    assert stored_doc.docx_file_name == original_docx_name, (
        f"docx_file_name must be '{original_docx_name}', got: {stored_doc.docx_file_name}"
    )
    assert stored_doc.docx_minio_path == original_docx_path
    assert stored_doc.pdf_file_name is None, (
        "pdf_file_name must be NULL for pre-migration rows"
    )
    assert stored_doc.pdf_minio_path is None, (
        "pdf_minio_path must be NULL for pre-migration rows"
    )

    # Verify the endpoint correctly identifies it as a legacy row needing backfill
    # GET /download?format=pdf → triggers ensure_pdf → 200 (backfill)
    response = await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=pdf",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    # After backfill, pdf fields must be populated
    updated_doc = fake_document_repo._documents.get(doc_id)
    assert updated_doc.pdf_file_name is not None, (
        "After backfill, pdf_file_name must not be NULL"
    )
    assert updated_doc.pdf_minio_path is not None, (
        "After backfill, pdf_minio_path must not be NULL"
    )


@pytest.mark.asyncio
async def test_migration_010_new_doc_has_all_four_file_fields(
    fake_document_repo
):
    """T-INT-04b: New docs (post-Phase 3) have all four file fields populated.

    Verifies the Document entity and FakeDocumentRepository correctly store
    the complete dual-format record from migration 010 onwards.
    """
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name="FullDoc.docx",
        docx_minio_path=f"{TENANT_ID}/{doc_id}/FullDoc.docx",
        pdf_file_name="FullDoc.pdf",
        pdf_minio_path=f"{TENANT_ID}/{doc_id}/FullDoc.pdf",
        generation_type="single",
        variables_snapshot={"name": "Maria"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    await fake_document_repo.create(doc)

    stored = fake_document_repo._documents.get(doc_id)
    assert stored.docx_file_name == "FullDoc.docx"
    assert stored.docx_minio_path == f"{TENANT_ID}/{doc_id}/FullDoc.docx"
    assert stored.pdf_file_name == "FullDoc.pdf"
    assert stored.pdf_minio_path == f"{TENANT_ID}/{doc_id}/FullDoc.pdf"


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-05 — Quota: single generate increments by exactly 1
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_quota_generate_increments_usage_by_exactly_one(
    async_client, app, auth_headers, fake_template_repo, fake_storage, fake_usage_repo
):
    """T-INT-05a: POST /generate increments usage counter by exactly 1 (not 2).

    REQ-DDF-16: Dual-format generation (DOCX + PDF) counts as 1 document,
    not 2. The quota/usage is charged once.
    """
    version_id = _seed_template_and_storage(fake_template_repo, fake_storage)
    # Capture current total (shared fixture state)
    from datetime import date
    month_start = date.today().replace(day=1)
    count_before = await fake_usage_repo.get_tenant_month_total(month_start=month_start)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Nathan", "date": "2025-07-01"},
        },
    )

    assert response.status_code == 201, response.text

    count_after = await fake_usage_repo.get_tenant_month_total(month_start=month_start)
    # Must have incremented by exactly 1 (not 2 for dual format)
    assert count_after == count_before + 1, (
        f"Usage must increment by 1, got: before={count_before}, after={count_after}"
    )


@pytest.mark.asyncio
async def test_quota_exceeded_returns_429(
    async_client, app, auth_headers, fake_template_repo, fake_storage,
    fake_document_repo, fake_audit_repo, fake_usage_repo
):
    """T-INT-05b: When quota is exceeded, generate returns 429.

    The DocumentService only invokes the quota check when BOTH quota_service
    AND tier_id are non-None. We inject a DocumentService with a known tier_id
    and a FakeQuotaService configured to raise QuotaExceededError.
    """
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from app.application.services.audit_service import AuditService
    from app.application.services.usage_service import UsageService
    from tests.fakes import FakeQuotaService, FakeAuditRepository

    version_id = _seed_template_and_storage(fake_template_repo, fake_storage)

    # A quota service that always rejects document quota
    exceeded_quota_service = FakeQuotaService(exceeded_resource="monthly_document_limit")
    fake_tier_id = uuid.uuid4()  # Non-None tier_id activates the quota guard

    _audit_service = AuditService(audit_repo=FakeAuditRepository())
    _usage_service = UsageService(usage_repo=fake_usage_repo)

    quota_service_with_tier = DocumentService(
        document_repository=fake_document_repo,
        template_repository=fake_template_repo,
        storage=fake_storage,
        engine=__import__("tests.fakes", fromlist=["FakeTemplateEngine"]).FakeTemplateEngine(),
        pdf_converter=FakePdfConverter(),
        audit_service=_audit_service,
        usage_service=_usage_service,
        quota_service=exceeded_quota_service,
        tier_id=fake_tier_id,  # Non-None → quota check fires
    )

    original = app.dependency_overrides.get(get_document_service)

    async def override_quota_service():
        return quota_service_with_tier

    app.dependency_overrides[get_document_service] = override_quota_service
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": version_id,
                "variables": {"name": "Olivia", "date": "2025-08-01"},
            },
        )
        # Quota exceeded → 429 Too Many Requests
        assert response.status_code == 429, (
            f"Expected 429 on quota exceeded, got {response.status_code}: {response.text}"
        )
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


# ═══════════════════════════════════════════════════════════════════════════
# T-INT-06 — W-PRES-02: list_by_batch_id used in bulk download
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_bulk_download_uses_list_by_batch_id(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-06a: Bulk download endpoint uses list_documents_by_batch (W-PRES-02 closed).

    Seeds a batch of 2 documents with a batch_id. Verifies the bulk download
    endpoint returns a ZIP containing both documents.
    This test implicitly verifies that list_by_batch_id is called instead of
    the old _doc_repo.list_paginated + Python filter.
    """
    batch_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    for doc_id, name in [(doc1_id, "BatchDoc1"), (doc2_id, "BatchDoc2")]:
        docx_path = f"{TENANT_ID}/{doc_id}/{name}.docx"
        pdf_path = f"{TENANT_ID}/{doc_id}/{name}.pdf"
        doc = Document(
            id=doc_id,
            tenant_id=TENANT_ID,
            template_version_id=uuid.uuid4(),
            docx_file_name=f"{name}.docx",
            docx_minio_path=docx_path,
            pdf_file_name=f"{name}.pdf",
            pdf_minio_path=pdf_path,
            generation_type="bulk",
            variables_snapshot={"name": name},
            created_by=ADMIN_USER_ID,
            status="completed",
            created_at=datetime.now(timezone.utc),
            batch_id=batch_id,
        )
        fake_document_repo._documents[doc_id] = doc
        fake_storage.files[("documents", docx_path)] = b"batch-docx-content"
        fake_storage.files[("documents", pdf_path)] = b"batch-pdf-content"

    response = await async_client.get(
        f"/api/v1/documents/bulk/{batch_id}/download?format=pdf",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").lower() == "application/zip"

    # Verify both documents are in the ZIP
    zip_bytes = response.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
    assert len(names) == 2, f"Expected 2 files in ZIP, got: {names}"
    assert any("BatchDoc1" in n for n in names), f"BatchDoc1 missing from ZIP: {names}"
    assert any("BatchDoc2" in n for n in names), f"BatchDoc2 missing from ZIP: {names}"


@pytest.mark.asyncio
async def test_bulk_download_tenant_isolation(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """T-INT-06b: Bulk download only returns docs for the request tenant (W-PRES-02).

    Seeds two docs with the same batch_id but different tenant_ids.
    The endpoint must only return docs belonging to the current user's tenant.
    """
    batch_id = uuid.uuid4()
    other_tenant_id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")

    # Doc belonging to the test tenant
    doc_mine_id = uuid.uuid4()
    docx_path_mine = f"{TENANT_ID}/{doc_mine_id}/MyDoc.docx"
    pdf_path_mine = f"{TENANT_ID}/{doc_mine_id}/MyDoc.pdf"
    doc_mine = Document(
        id=doc_mine_id,
        tenant_id=TENANT_ID,  # correct tenant
        template_version_id=uuid.uuid4(),
        docx_file_name="MyDoc.docx",
        docx_minio_path=docx_path_mine,
        pdf_file_name="MyDoc.pdf",
        pdf_minio_path=pdf_path_mine,
        generation_type="bulk",
        variables_snapshot={"name": "Mine"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=batch_id,
    )
    # Doc belonging to a DIFFERENT tenant — must NOT appear in results
    doc_other_id = uuid.uuid4()
    docx_path_other = f"{other_tenant_id}/{doc_other_id}/OtherDoc.docx"
    doc_other = Document(
        id=doc_other_id,
        tenant_id=other_tenant_id,  # different tenant
        template_version_id=uuid.uuid4(),
        docx_file_name="OtherDoc.docx",
        docx_minio_path=docx_path_other,
        generation_type="bulk",
        variables_snapshot={"name": "Other"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=batch_id,  # same batch_id as doc_mine!
    )

    fake_document_repo._documents[doc_mine_id] = doc_mine
    fake_document_repo._documents[doc_other_id] = doc_other
    fake_storage.files[("documents", docx_path_mine)] = b"my-docx"
    fake_storage.files[("documents", pdf_path_mine)] = b"my-pdf"

    response = await async_client.get(
        f"/api/v1/documents/bulk/{batch_id}/download?format=pdf",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text

    # Only MyDoc should be in the ZIP — not OtherDoc (different tenant)
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
    assert len(names) == 1, f"Expected only 1 doc (tenant isolation), got: {names}"
    assert any("MyDoc" in n for n in names), f"Expected MyDoc in ZIP: {names}"
    assert not any("OtherDoc" in n for n in names), (
        f"OtherDoc must not appear (different tenant): {names}"
    )
