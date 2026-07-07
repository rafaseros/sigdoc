"""Unit tests for DocumentService.preview() — ephemeral true-fidelity preview.

Covers the ephemeral document preview feature: renders the current
(possibly partial) variable values against a template and returns the
converted PDF bytes directly. Nothing is persisted.

Strict TDD order: this test file is written first (RED), then
DocumentService.preview() is implemented (GREEN).

All tests use fakes / AsyncMock doubles so they run without Gotenberg,
MinIO, or a real DB.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.document_service import DocumentService
from app.domain.entities import Template, TemplateVersion
from app.domain.exceptions import (
    PdfConversionError,
    TemplateAccessDeniedError,
    TemplateVersionNotFoundError,
)
from tests.fakes import (
    FakePdfConverter,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def passthrough_watermark(monkeypatch):
    """Make apply_watermark a no-op pass-through by default.

    preview() now runs every PDF through apply_watermark(). Tests in this
    file that predate the watermark feature assert on the RAW converter
    output, so this autouse fixture keeps that behavior working. Tests that
    specifically exercise the watermark wiring (TestPreviewWatermark below)
    override this patch with their own mock.
    """
    monkeypatch.setattr(
        "app.application.services.document_service.apply_watermark",
        lambda pdf_bytes, text: pdf_bytes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingTemplateEngine(FakeTemplateEngine):
    """FakeTemplateEngine that records the exact variables dict passed to render()."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.render_calls: list[dict[str, str]] = []

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        self.render_calls.append(variables)
        return await super().render(file_bytes, variables)


def make_service(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
    pdf_converter: FakePdfConverter,
    doc_repo=None,
    usage_service=None,
    audit_service=None,
    quota_service=None,
    tier_id=None,
) -> DocumentService:
    """Build a DocumentService with AsyncMock spies for the collaborators
    that preview() MUST NOT touch (doc_repo, usage_service, audit_service),
    so tests can assert_not_called() on them.
    """
    return DocumentService(
        document_repository=doc_repo if doc_repo is not None else AsyncMock(),
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
        pdf_converter=pdf_converter,
        usage_service=usage_service,
        audit_service=audit_service,
        quota_service=quota_service,
        tier_id=tier_id,
    )


def seed_version(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    variables: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
) -> tuple[TemplateVersion, str, str, str]:
    """Seed a template + version + template bytes.

    Returns (version, version_id_str, tenant_id_str, owner_id_str).
    """
    if variables is None:
        variables = ["name", "company", "date"]

    tenant_id = uuid.uuid4()
    owner_uuid = owner_id if owner_id is not None else uuid.uuid4()
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
        created_by=owner_uuid,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    tpl_repo._templates[template_id] = template

    storage.files[("templates", version.minio_path)] = b"fake-docx-bytes"
    return version, str(version_id), str(tenant_id), str(owner_uuid)


# ---------------------------------------------------------------------------
# preview() — happy path
# ---------------------------------------------------------------------------


class TestPreviewHappyPath:
    async def test_preview_returns_converter_pdf_bytes(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """preview() returns exactly the bytes produced by the PDF converter."""
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter(convert_result=b"the-preview-pdf-bytes")
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        result = await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        assert result == b"the-preview-pdf-bytes"

    async def test_preview_calls_engine_with_variables_verbatim(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """The engine's render() receives the partial variables dict verbatim
        (no padding, no defaults injected by the service)."""
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(
            fake_template_repo, fake_storage, variables=["name", "company", "date"]
        )

        partial_variables = {"name": "Alice"}  # only 1 of 3 template variables
        await service.preview(
            template_version_id=version_id,
            variables=partial_variables,
            user_id=owner_id,
            role="user",
        )

        assert len(engine.render_calls) == 1
        assert engine.render_calls[0] == partial_variables


# ---------------------------------------------------------------------------
# preview() — must NOT persist anything
# ---------------------------------------------------------------------------


class TestPreviewDoesNotPersist:
    async def test_does_not_call_doc_repo_create(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        doc_repo = AsyncMock()
        service = make_service(
            fake_template_repo, fake_storage, engine, pdf_converter, doc_repo=doc_repo
        )
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        doc_repo.create.assert_not_called()

    async def test_does_not_call_usage_service_record(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        usage_service = AsyncMock()
        service = make_service(
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter,
            usage_service=usage_service,
        )
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        usage_service.record.assert_not_called()

    async def test_does_not_call_audit_service_log(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        audit_service = MagicMock()
        service = make_service(
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter,
            audit_service=audit_service,
        )
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        audit_service.log.assert_not_called()

    async def test_does_not_call_storage_upload_file(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """download_file MUST be called (to fetch the template); upload_file
        MUST NOT be called (nothing is persisted)."""
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        # Spy on upload_file while keeping the real in-memory behavior for
        # download_file (needed to fetch the seeded template bytes).
        fake_storage.upload_file = AsyncMock(wraps=fake_storage.upload_file)
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        fake_storage.upload_file.assert_not_called()

    async def test_does_not_check_quota(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """Even when a quota_service + tier_id are configured on the service,
        preview() must never call quota checks (it is ephemeral, not counted)."""
        from app.domain.entities.subscription_tier import FREE_TIER_ID

        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()

        class PoisonQuotaService:
            async def check_document_quota(self, *args, **kwargs):
                raise AssertionError("preview() must not check document quota")

            async def check_bulk_limit(self, *args, **kwargs):
                raise AssertionError("preview() must not check bulk limit")

        service = make_service(
            fake_template_repo,
            fake_storage,
            engine,
            pdf_converter,
            quota_service=PoisonQuotaService(),
            tier_id=FREE_TIER_ID,
        )
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        # Must complete without raising — proves quota check was never invoked.
        await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )


# ---------------------------------------------------------------------------
# preview() — error handling, shared with generate_single
# ---------------------------------------------------------------------------


class TestPreviewErrorHandling:
    async def test_version_not_found_raises_same_exception_as_generate(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)

        with pytest.raises(TemplateVersionNotFoundError):
            await service.preview(
                template_version_id=str(uuid.uuid4()),
                variables={"name": "Alice"},
                user_id=str(uuid.uuid4()),
                role="user",
            )

    async def test_access_denied_raises_same_exception_as_generate(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        unrelated_user_id = str(uuid.uuid4())  # not owner, no share, non-admin

        with pytest.raises(TemplateAccessDeniedError):
            await service.preview(
                template_version_id=version_id,
                variables={"name": "Alice"},
                user_id=unrelated_user_id,
                role="user",
            )

    async def test_pdf_conversion_error_propagates(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        pdf_converter.set_failure(PdfConversionError("Gotenberg unavailable"))
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        with pytest.raises(PdfConversionError):
            await service.preview(
                template_version_id=version_id,
                variables={"name": "Alice"},
                user_id=owner_id,
                role="user",
            )


# ---------------------------------------------------------------------------
# preview() — server-side watermark wiring
# ---------------------------------------------------------------------------


class TestPreviewWatermark:
    async def test_preview_applies_watermark_to_converter_output(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        monkeypatch,
    ):
        """preview() must run the converter's output through apply_watermark
        (imported into document_service) with the service's configured
        watermark text, and return exactly what apply_watermark returns."""
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter(convert_result=b"converter-output-bytes")
        watermark_mock = MagicMock(return_value=b"watermarked-bytes")
        monkeypatch.setattr(
            "app.application.services.document_service.apply_watermark",
            watermark_mock,
        )
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, _, owner_id = seed_version(fake_template_repo, fake_storage)

        result = await service.preview(
            template_version_id=version_id,
            variables={"name": "Alice"},
            user_id=owner_id,
            role="user",
        )

        watermark_mock.assert_called_once_with(
            b"converter-output-bytes", service._preview_watermark_text
        )
        assert result == b"watermarked-bytes"

    async def test_generate_single_does_not_call_apply_watermark(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        monkeypatch,
    ):
        """Final generation paths must remain untouched — no watermark
        there, ever."""
        engine = RecordingTemplateEngine()
        pdf_converter = FakePdfConverter()
        watermark_mock = MagicMock(return_value=b"should-not-be-used")
        monkeypatch.setattr(
            "app.application.services.document_service.apply_watermark",
            watermark_mock,
        )
        service = make_service(fake_template_repo, fake_storage, engine, pdf_converter)
        _, version_id, tenant_id, owner_id = seed_version(fake_template_repo, fake_storage)

        await service.generate_single(
            template_version_id=version_id,
            variables={"name": "Alice"},
            tenant_id=tenant_id,
            created_by=owner_id,
            role="user",
        )

        watermark_mock.assert_not_called()
