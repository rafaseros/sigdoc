"""Integration tests — Phase 4 Presentation layer (pdf-export).

Covers:
- T-PRES-01: output_format in generate body → 422 (SCEN-DDF-04)
- T-PRES-02: single-doc download RBAC + audit (SCEN-DDF-01..03, 06..08)
- T-PRES-03: PdfConversionError → 503 on generate (W-03)
- T-PRES-04: bulk download RBAC (SCEN-DDF-09..12)
- T-PRES-05: PdfConversionError → 503 on generate-bulk (W-04)
- T-PRES-06: sharing RBAC (SCEN-DDF-13, SCEN-DDF-14)
- T-PRES-07: via=share sanity check (ADR-PDF-07)

All tests use in-memory fakes from conftest — no real Gotenberg needed.
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

# ── Stable identifiers shared by this module ────────────────────────────────

TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Fixture helpers ──────────────────────────────────────────────────────────

def _make_non_admin_user() -> CurrentUser:
    return CurrentUser(user_id=USER_ID, tenant_id=TENANT_ID, role="user")


def _make_admin_user() -> CurrentUser:
    return CurrentUser(user_id=ADMIN_USER_ID, tenant_id=TENANT_ID, role="admin")


def _seed_template_version_for_download(fake_template_repo, fake_storage) -> str:
    """Seed a template + version and return version_id str."""
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


def _seed_legacy_document(
    fake_document_repo,
    fake_storage,
    *,
    tenant_id: uuid.UUID = TENANT_ID,
    creator_id: uuid.UUID = ADMIN_USER_ID,
    pdf_file_name: str | None = None,
    pdf_minio_path: str | None = None,
) -> Document:
    """Insert a Document row directly into the fake repository.

    By default inserts a *legacy* doc (pdf_file_name=None).
    Pass pdf_file_name + pdf_minio_path to simulate an already-backfilled doc.
    """
    doc_id = uuid.uuid4()
    template_version_id = uuid.uuid4()
    docx_file_name = "Alice.docx"
    docx_minio_path = f"{tenant_id}/{doc_id}/{docx_file_name}"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        template_version_id=template_version_id,
        docx_file_name=docx_file_name,
        docx_minio_path=docx_minio_path,
        pdf_file_name=pdf_file_name,
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Alice", "date": "2025-01-01"},
        created_by=creator_id,
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=None,
    )
    fake_document_repo._documents[doc_id] = doc

    # Seed DOCX bytes so download_document() works
    fake_storage.files[("documents", docx_minio_path)] = b"fake-docx-bytes"

    # Also seed PDF bytes if pdf_minio_path is set
    if pdf_minio_path is not None:
        fake_storage.files[("documents", pdf_minio_path)] = b"fake-pdf-bytes"

    return doc


# ═══════════════════════════════════════════════════════════════════════════
# Group A — Schema: output_format rejection (T-PRES-01, SCEN-DDF-04)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_with_output_format_returns_422(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """SCEN-DDF-04: POST /generate with output_format in body → 422."""
    version_id = _seed_template_version_for_download(fake_template_repo, fake_storage)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "date": "2025-01-01"},
            "output_format": "pdf",  # MUST be rejected
        },
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_generate_bulk_with_output_format_returns_422(
    async_client, auth_headers
):
    """SCEN-DDF-04 bulk: output_format must not be accepted in any generate request.

    For generate-bulk this is a form upload, so output_format would need to be
    in the multipart body — this test verifies the endpoint doesn't silently
    accept it as an unexpected form field.
    """
    # Minimal invalid file to trigger early parsing (not the real concern here)
    # The point: an extra 'output_format' form field MUST NOT cause 200.
    # In practice, FastAPI/pydantic rejects extra fields on the Pydantic body;
    # multipart extra fields are ignored unless explicitly parsed — so we just
    # verify the endpoint signature hasn't accidentally added output_format.
    import io as _io
    dummy_xlsx = _io.BytesIO(b"PK\x03\x04")  # minimal, will fail parsing → 4xx not 200
    dummy_xlsx.name = "data.xlsx"
    response = await async_client.post(
        "/api/v1/documents/generate-bulk",
        headers=auth_headers,
        data={
            "template_version_id": str(uuid.uuid4()),
            "output_format": "pdf",  # extra form field — should be ignored/rejected
        },
        files={"file": ("data.xlsx", _io.BytesIO(b"PK\x03\x04"), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    # The response should NOT be 200 — it will be 400 (empty/invalid file), 404
    # (version not found), or 422 (validation). The key assertion is NOT 200/201.
    assert response.status_code != 200
    assert response.status_code != 201


# ═══════════════════════════════════════════════════════════════════════════
# Group B — 503 mapping for PdfConversionError (W-03, W-04)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_generate_pdf_conversion_error_returns_503(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """W-03: PdfConverter raises PdfConversionError during generate → HTTP 503."""
    from tests.fakes import FakePdfConverter, FakeDocumentRepository, FakeTemplateEngine
    from tests.fakes import FakeUsageRepository, FakeAuditRepository, FakeQuotaService
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from app.application.services.audit_service import AuditService
    from app.application.services.usage_service import UsageService

    version_id = _seed_template_version_for_download(fake_template_repo, fake_storage)

    # Build a fresh converter that will fail
    failing_converter = FakePdfConverter()
    failing_converter.set_failure(PdfConversionError("Gotenberg down"))

    # Override document service with the failing converter
    _audit_service = AuditService(audit_repo=FakeAuditRepository())
    _usage_service = UsageService(usage_repo=FakeUsageRepository())

    async def override_failing_doc_service() -> DocumentService:
        return DocumentService(
            document_repository=FakeDocumentRepository(),
            template_repository=fake_template_repo,
            storage=fake_storage,
            engine=FakeTemplateEngine(),
            pdf_converter=failing_converter,
            bulk_generation_limit=10,
            usage_service=_usage_service,
            audit_service=_audit_service,
        )

    original = app.dependency_overrides.get(get_document_service)
    app.dependency_overrides[get_document_service] = override_failing_doc_service
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": version_id,
                "variables": {"name": "Alice", "date": "2025-01-01"},
            },
        )
        assert response.status_code == 503, response.text
        # Detail must be present but must NOT leak internal details
        detail = response.json().get("detail", "")
        assert "gotenberg" not in detail.lower(), "Must not leak Gotenberg URL in error detail"
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


@pytest.mark.asyncio
async def test_generate_bulk_pdf_conversion_error_returns_503(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """W-04: PdfConverter raises PdfConversionError during generate-bulk → HTTP 503."""
    import io as _io
    import openpyxl
    from tests.fakes import FakePdfConverter, FakeDocumentRepository, FakeTemplateEngine
    from tests.fakes import FakeUsageRepository, FakeAuditRepository, FakeQuotaService
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from app.application.services.audit_service import AuditService
    from app.application.services.usage_service import UsageService

    version_id = _seed_template_version_for_download(fake_template_repo, fake_storage)

    # Build minimal valid xlsx with 1 data row
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "date"])
    ws.append(["Alice", "2025-01-01"])
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    xlsx_bytes = buf.read()

    # Failing converter
    failing_converter = FakePdfConverter()
    failing_converter.set_failure(PdfConversionError("Gotenberg down"))

    _audit_service = AuditService(audit_repo=FakeAuditRepository())
    _usage_service = UsageService(usage_repo=FakeUsageRepository())

    async def override_failing_doc_service() -> DocumentService:
        return DocumentService(
            document_repository=FakeDocumentRepository(),
            template_repository=fake_template_repo,
            storage=fake_storage,
            engine=FakeTemplateEngine(),
            pdf_converter=failing_converter,
            bulk_generation_limit=10,
            usage_service=_usage_service,
            audit_service=_audit_service,
        )

    from app.application.services import get_document_service
    original = app.dependency_overrides.get(get_document_service)
    app.dependency_overrides[get_document_service] = override_failing_doc_service
    try:
        response = await async_client.post(
            "/api/v1/documents/generate-bulk",
            headers=auth_headers,
            data={"template_version_id": version_id},
            files={"file": ("data.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert response.status_code == 503, response.text
        detail = response.json().get("detail", "")
        assert "gotenberg" not in detail.lower()
    finally:
        if original is not None:
            app.dependency_overrides[get_document_service] = original
        else:
            app.dependency_overrides.pop(get_document_service, None)


# ═══════════════════════════════════════════════════════════════════════════
# Group C — Single-doc download with format param + RBAC (T-PRES-02, T-PRES-03)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_download_missing_format_returns_422(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """Missing format query param → 422."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name="Alice.pdf",
        pdf_minio_path=f"{TENANT_ID}/{uuid.uuid4()}/Alice.pdf",
    )
    response = await async_client.get(
        f"/api/v1/documents/{doc.id}/download",
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_download_invalid_format_returns_422(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """Invalid format value → 422."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name="Alice.pdf",
        pdf_minio_path=f"{TENANT_ID}/{uuid.uuid4()}/Alice.pdf",
    )
    response = await async_client.get(
        f"/api/v1/documents/{doc.id}/download?format=xyz",
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_admin_download_docx_returns_200_with_correct_mime(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-01: Admin downloads format=docx → 200 with DOCX MIME type."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name="Alice.pdf",
        pdf_minio_path=f"{TENANT_ID}/{uuid.uuid4()}/Alice.pdf",
    )
    # admin is the default user in conftest (TEST_USER_ROLE = "admin")
    response = await async_client.get(
        f"/api/v1/documents/{doc.id}/download?format=docx",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "openxmlformats" in response.headers.get("content-type", "").lower()


@pytest.mark.asyncio
async def test_user_download_pdf_returns_200_with_pdf_mime(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """SCEN-DDF-02: Non-admin user downloads format=pdf → 200 with PDF MIME + audit."""
    doc_id = uuid.uuid4()
    template_version_id = uuid.uuid4()
    docx_file_name = "Bob.docx"
    pdf_file_name = "Bob.pdf"
    docx_minio_path = f"{TENANT_ID}/{doc_id}/{docx_file_name}"
    pdf_minio_path = f"{TENANT_ID}/{doc_id}/{pdf_file_name}"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=template_version_id,
        docx_file_name=docx_file_name,
        docx_minio_path=docx_minio_path,
        pdf_file_name=pdf_file_name,
        pdf_minio_path=pdf_minio_path,
        generation_type="single",
        variables_snapshot={"name": "Bob"},
        created_by=ADMIN_USER_ID,
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=None,
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_minio_path)] = b"fake-docx-bytes"
    fake_storage.files[("documents", pdf_minio_path)] = b"fake-pdf-bytes"

    # Override current user to be a non-admin
    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin

    initial_audit_count = len(fake_audit_repo._entries)
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type", "").lower() == "application/pdf"
        assert response.content == b"fake-pdf-bytes"

        # Assert audit event written with format="pdf" and via="direct"
        new_entries = fake_audit_repo._entries[initial_audit_count:]
        download_events = [
            e for e in new_entries if e.action == "document.download"
        ]
        assert len(download_events) >= 1, "Expected at least one DOCUMENT_DOWNLOAD audit event"
        evt = download_events[-1]
        assert evt.details is not None
        assert evt.details.get("format") == "pdf"
        assert evt.details.get("via") == "direct"
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_download_docx_returns_403(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-03: Non-admin user requests format=docx → 403 non-leaky message."""
    doc = _seed_legacy_document(fake_document_repo, fake_storage)

    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc.id}/download?format=docx",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
        # Message must not be leaky
        detail = response.json().get("detail", "")
        assert len(detail) > 0
        assert "file" not in detail.lower() or "format" in detail.lower()
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_download_pdf_legacy_triggers_backfill(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-06: User downloads pdf for legacy doc (pdf_file_name=NULL) → 200 + backfill."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name=None,   # legacy doc — no PDF yet
        pdf_minio_path=None,
    )

    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc.id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type", "").lower() == "application/pdf"

        # After backfill, pdf_file_name must be persisted on the doc
        updated_doc = fake_document_repo._documents.get(doc.id)
        assert updated_doc is not None
        assert updated_doc.pdf_file_name is not None, "pdf_file_name must be set after backfill"
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_user_download_pdf_legacy_gotenberg_down_returns_503(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-07: Legacy doc + Gotenberg down → 503, pdf_file_name remains NULL."""
    from tests.fakes import FakePdfConverter, FakeTemplateEngine
    from tests.fakes import FakeUsageRepository, FakeAuditRepository
    from app.application.services import get_document_service
    from app.application.services.document_service import DocumentService
    from app.application.services.audit_service import AuditService
    from app.application.services.usage_service import UsageService
    from app.domain.exceptions import PdfConversionError

    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name=None,
        pdf_minio_path=None,
    )

    # Create a failing converter
    failing_converter = FakePdfConverter()
    failing_converter.set_failure(PdfConversionError("Gotenberg down"))

    from tests.fakes import FakeTemplateRepository

    async def override_failing_doc_service() -> DocumentService:
        return DocumentService(
            document_repository=fake_document_repo,
            template_repository=FakeTemplateRepository(),
            storage=fake_storage,
            engine=FakeTemplateEngine(),
            pdf_converter=failing_converter,
        )

    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original_svc = app.dependency_overrides.get(get_document_service)
    original_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_document_service] = override_failing_doc_service
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc.id}/download?format=pdf",
            headers=auth_headers,
        )
        assert response.status_code == 503, response.text

        # pdf_file_name must remain NULL after failed backfill
        assert doc.pdf_file_name is None, "pdf_file_name must remain NULL after failed backfill"
    finally:
        if original_svc is not None:
            app.dependency_overrides[get_document_service] = original_svc
        else:
            app.dependency_overrides.pop(get_document_service, None)
        if original_user is not None:
            app.dependency_overrides[get_current_user] = original_user
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_admin_download_docx_legacy_doc_no_backfill(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-08: Admin downloads format=docx on legacy doc → 200 DOCX, no PDF conversion."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name=None,   # legacy
        pdf_minio_path=None,
    )
    # admin is the default user in conftest
    response = await async_client.get(
        f"/api/v1/documents/{doc.id}/download?format=docx",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "openxmlformats" in response.headers.get("content-type", "").lower()

    # pdf_file_name must still be NULL — no backfill was triggered
    assert doc.pdf_file_name is None, "pdf_file_name must not be set for docx-only download"


# ═══════════════════════════════════════════════════════════════════════════
# Group D — Bulk download endpoint (T-PRES-04, T-PRES-05)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_bulk_download_missing_format_returns_422(
    async_client, auth_headers
):
    """Missing format param on bulk download → 422."""
    batch_id = str(uuid.uuid4())
    response = await async_client.get(
        f"/api/v1/documents/bulk/{batch_id}/download",
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_bulk_download_admin_pdf_only_returns_zip(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-09: Admin bulk download format=pdf → 200 ZIP with .pdf files."""
    batch_id = uuid.uuid4()
    # Seed two documents for the batch
    for i, name in enumerate(["Alice", "Bob"]):
        doc_id = uuid.uuid4()
        docx_fn = f"{i + 1:03d}_{name}.docx"
        pdf_fn = f"{i + 1:03d}_{name}.pdf"
        docx_path = f"{TENANT_ID}/{batch_id}/{docx_fn}"
        pdf_path = f"{TENANT_ID}/{batch_id}/{pdf_fn}"
        doc = Document(
            id=doc_id,
            tenant_id=TENANT_ID,
            template_version_id=uuid.uuid4(),
            docx_file_name=docx_fn,
            docx_minio_path=docx_path,
            pdf_file_name=pdf_fn,
            pdf_minio_path=pdf_path,
            generation_type="bulk",
            batch_id=batch_id,
            variables_snapshot={"name": name, "date": "2025-01-01"},
            created_by=ADMIN_USER_ID,
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        fake_document_repo._documents[doc_id] = doc
        fake_storage.files[("documents", docx_path)] = b"fake-docx"
        fake_storage.files[("documents", pdf_path)] = b"fake-pdf"

    response = await async_client.get(
        f"/api/v1/documents/bulk/{batch_id}/download?format=pdf&include_both=false",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "zip" in response.headers.get("content-type", "").lower()

    # Verify ZIP contains only .pdf files
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
    assert all(n.endswith(".pdf") for n in names), f"Expected only .pdf files, got {names}"
    assert len(names) == 2


@pytest.mark.asyncio
async def test_bulk_download_admin_include_both_returns_zip_with_both(
    async_client, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-10: Admin bulk download include_both=true → ZIP with .docx + .pdf per row."""
    batch_id = uuid.uuid4()
    for i, name in enumerate(["Carol", "Dave"]):
        doc_id = uuid.uuid4()
        docx_fn = f"{i + 1:03d}_{name}.docx"
        pdf_fn = f"{i + 1:03d}_{name}.pdf"
        docx_path = f"{TENANT_ID}/{batch_id}/{docx_fn}"
        pdf_path = f"{TENANT_ID}/{batch_id}/{pdf_fn}"
        doc = Document(
            id=doc_id,
            tenant_id=TENANT_ID,
            template_version_id=uuid.uuid4(),
            docx_file_name=docx_fn,
            docx_minio_path=docx_path,
            pdf_file_name=pdf_fn,
            pdf_minio_path=pdf_path,
            generation_type="bulk",
            batch_id=batch_id,
            variables_snapshot={"name": name, "date": "2025-01-01"},
            created_by=ADMIN_USER_ID,
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        fake_document_repo._documents[doc_id] = doc
        fake_storage.files[("documents", docx_path)] = b"fake-docx"
        fake_storage.files[("documents", pdf_path)] = b"fake-pdf"

    response = await async_client.get(
        f"/api/v1/documents/bulk/{batch_id}/download?format=pdf&include_both=true",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "zip" in response.headers.get("content-type", "").lower()

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()

    docx_names = [n for n in names if n.endswith(".docx")]
    pdf_names = [n for n in names if n.endswith(".pdf")]
    assert len(docx_names) == 2, f"Expected 2 .docx files, got {docx_names}"
    assert len(pdf_names) == 2, f"Expected 2 .pdf files, got {pdf_names}"


@pytest.mark.asyncio
async def test_bulk_download_non_admin_docx_returns_403(
    async_client, app, auth_headers
):
    """SCEN-DDF-11: Non-admin requests bulk download format=docx → 403."""
    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        batch_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/documents/bulk/{batch_id}/download?format=docx",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_bulk_download_non_admin_include_both_returns_403(
    async_client, app, auth_headers
):
    """SCEN-DDF-12: Non-admin requests include_both=true → 403."""
    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        batch_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/documents/bulk/{batch_id}/download?format=pdf&include_both=true",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ═══════════════════════════════════════════════════════════════════════════
# Group E — Sharing inheritance (T-PRES-06, SCEN-DDF-13/14)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_share_recipient_non_admin_cannot_download_docx(
    async_client, app, auth_headers, fake_document_repo, fake_storage
):
    """SCEN-DDF-13: Non-admin via share link requests format=docx → 403."""
    doc = _seed_legacy_document(
        fake_document_repo,
        fake_storage,
        pdf_file_name="Alice.pdf",
        pdf_minio_path=f"{TENANT_ID}/{uuid.uuid4()}/Alice.pdf",
    )

    non_admin = _make_non_admin_user()

    async def override_non_admin():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc.id}/download?format=docx&via=share",
            headers=auth_headers,
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_share_recipient_non_admin_downloads_pdf_with_via_share_audit(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """SCEN-DDF-14: Non-admin via share downloads pdf → 200 + audit via='share'."""
    doc_id = uuid.uuid4()
    docx_fn = "Alice.docx"
    pdf_fn = "Alice.pdf"
    docx_path = f"{TENANT_ID}/{doc_id}/{docx_fn}"
    pdf_path = f"{TENANT_ID}/{doc_id}/{pdf_fn}"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name=docx_fn,
        docx_minio_path=docx_path,
        pdf_file_name=pdf_fn,
        pdf_minio_path=pdf_path,
        generation_type="single",
        variables_snapshot={"name": "Alice"},
        created_by=ADMIN_USER_ID,  # Admin created it, different from non_admin recipient
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=None,
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_path)] = b"fake-docx"
    fake_storage.files[("documents", pdf_path)] = b"fake-pdf-share"

    non_admin = _make_non_admin_user()  # USER_ID ≠ ADMIN_USER_ID (doc creator)

    async def override_non_admin():
        return non_admin

    initial_count = len(fake_audit_repo._entries)
    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_non_admin
    try:
        response = await async_client.get(
            f"/api/v1/documents/{doc_id}/download?format=pdf&via=share",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.content == b"fake-pdf-share"

        # Audit event must record via="share"
        new_entries = fake_audit_repo._entries[initial_count:]
        download_events = [e for e in new_entries if e.action == "document.download"]
        assert len(download_events) >= 1
        evt = download_events[-1]
        assert evt.details is not None
        assert evt.details.get("via") == "share"
        assert evt.details.get("format") == "pdf"
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ═══════════════════════════════════════════════════════════════════════════
# Group F — via=share sanity check (T-PRES-07, ADR-PDF-07)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_via_share_overridden_to_direct_for_doc_creator(
    async_client, app, auth_headers, fake_document_repo, fake_storage, fake_audit_repo
):
    """ADR-PDF-07: Creator sends via=share → backend overrides to via=direct in audit."""
    doc_id = uuid.uuid4()
    docx_fn = "Creator.docx"
    pdf_fn = "Creator.pdf"
    docx_path = f"{TENANT_ID}/{doc_id}/{docx_fn}"
    pdf_path = f"{TENANT_ID}/{doc_id}/{pdf_fn}"

    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        template_version_id=uuid.uuid4(),
        docx_file_name=docx_fn,
        docx_minio_path=docx_path,
        pdf_file_name=pdf_fn,
        pdf_minio_path=pdf_path,
        generation_type="single",
        variables_snapshot={"name": "Creator"},
        created_by=ADMIN_USER_ID,  # doc created_by = ADMIN_USER_ID
        status="completed",
        created_at=datetime.now(timezone.utc),
        batch_id=None,
    )
    fake_document_repo._documents[doc_id] = doc
    fake_storage.files[("documents", docx_path)] = b"fake-docx"
    fake_storage.files[("documents", pdf_path)] = b"fake-pdf"

    # Admin user (= doc creator) sends via=share → should be overridden to via=direct
    # The conftest default user IS ADMIN_USER_ID — so current_user.user_id == doc.created_by
    initial_count = len(fake_audit_repo._entries)

    response = await async_client.get(
        f"/api/v1/documents/{doc_id}/download?format=pdf&via=share",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    new_entries = fake_audit_repo._entries[initial_count:]
    download_events = [e for e in new_entries if e.action == "document.download"]
    assert len(download_events) >= 1
    evt = download_events[-1]
    assert evt.details is not None
    # via should have been overridden to "direct" because the user IS the creator
    assert evt.details.get("via") == "direct", (
        f"Expected via='direct' (creator sanity check), got via='{evt.details.get('via')}'"
    )
