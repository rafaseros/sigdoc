"""Unit tests for computed-variable resolution wired into DocumentService.

Both generate_single() and preview() must resolve computed variables from
the template version's variables_meta AFTER receiving the caller-supplied
variables but BEFORE calling engine.render() — so the rendered document (and,
for generate_single, the persisted variables_snapshot) always reflects the
server-authoritative computed value.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import AsyncMock

import openpyxl
import pytest

from app.application.services.document_service import DocumentService
from app.domain.entities import Template, TemplateVersion
from app.domain.exceptions import ComputedVariableError
from tests.fakes import (
    FakeDocumentRepository,
    FakePdfConverter,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


@pytest.fixture(autouse=True)
def passthrough_watermark(monkeypatch):
    """preview() runs output through apply_watermark(); make it a no-op so
    tests can assert on the raw converter output, matching the convention in
    test_document_service_preview.py."""
    monkeypatch.setattr(
        "app.application.services.document_service.apply_watermark",
        lambda pdf_bytes, text: pdf_bytes,
    )


class RecordingTemplateEngine(FakeTemplateEngine):
    """FakeTemplateEngine that records the exact variables dict passed to render()."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.render_calls: list[dict[str, str]] = []

    async def render(self, file_bytes: bytes, variables: dict[str, str]) -> bytes:
        self.render_calls.append(dict(variables))
        return await super().render(file_bytes, variables)


def make_service(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
    doc_repo=None,
    pdf_converter=None,
) -> DocumentService:
    return DocumentService(
        document_repository=doc_repo if doc_repo is not None else AsyncMock(),
        template_repository=tpl_repo,
        storage=storage,
        engine=engine,
        pdf_converter=pdf_converter if pdf_converter is not None else FakePdfConverter(),
    )


def seed_version_with_computed(
    tpl_repo: FakeTemplateRepository,
    storage: FakeStorageService,
    variables_meta: list[dict],
    owner_id: uuid.UUID | None = None,
) -> tuple[TemplateVersion, str, str, str]:
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
        variables=[m["name"] for m in variables_meta],
        variables_meta=variables_meta,
        created_at=now,
    )
    tpl_repo._versions[version_id] = version

    template = Template(
        id=template_id,
        tenant_id=tenant_id,
        name="Test Template Computed",
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


FORMULA_META = [
    {"name": "monto", "type": "decimal", "contexts": []},
    {
        "name": "total_con_iva",
        "type": "decimal",
        "contexts": [],
        "computed": {"kind": "formula", "source": "monto", "operator": "+", "operand": 100},
    },
]

FUNCTION_META = [
    {"name": "monto", "type": "decimal", "contexts": []},
    {
        "name": "monto_en_letras",
        "type": "text",
        "contexts": [],
        "computed": {"kind": "function", "function": "number_to_words", "source": "monto"},
    },
]


class TestGenerateSingleResolvesComputed:
    async def test_engine_called_with_resolved_dict(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        await service.generate_single(
            template_version_id=version_id,
            variables={"monto": "400.00"},
            tenant_id=tenant_id,
            created_by=owner_id,
        )

        assert len(engine.render_calls) == 1
        assert engine.render_calls[0]["total_con_iva"] == "500.00"

    async def test_variables_snapshot_stores_resolved_values(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(
            fake_template_repo, fake_storage, engine, doc_repo=FakeDocumentRepository()
        )

        result = await service.generate_single(
            template_version_id=version_id,
            variables={"monto": "400.00"},
            tenant_id=tenant_id,
            created_by=owner_id,
        )

        assert result["documents"][0].variables_snapshot["total_con_iva"] == "500.00"

    async def test_user_supplied_value_for_computed_name_is_overwritten(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        await service.generate_single(
            template_version_id=version_id,
            variables={"monto": "400.00", "total_con_iva": "TAMPERED"},
            tenant_id=tenant_id,
            created_by=owner_id,
        )

        assert engine.render_calls[0]["total_con_iva"] == "500.00"

    async def test_number_to_words_function_resolved(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FUNCTION_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        await service.generate_single(
            template_version_id=version_id,
            variables={"monto": "1500.50"},
            tenant_id=tenant_id,
            created_by=owner_id,
        )

        assert engine.render_calls[0]["monto_en_letras"] == "UN MIL QUINIENTOS 50/100"

    async def test_negative_source_for_number_to_words_raises(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FUNCTION_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        with pytest.raises(ComputedVariableError):
            await service.generate_single(
                template_version_id=version_id,
                variables={"monto": "-5"},
                tenant_id=tenant_id,
                created_by=owner_id,
            )


class TestPreviewResolvesComputed:
    async def test_engine_called_with_resolved_dict(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        await service.preview(
            template_version_id=version_id,
            variables={"monto": "400.00"},
            user_id=owner_id,
        )

        assert len(engine.render_calls) == 1
        assert engine.render_calls[0]["total_con_iva"] == "500.00"

    async def test_partial_fill_missing_source_does_not_crash(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """Preview with the source variable not yet filled in must not
        crash — the computed value resolves to empty string."""
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        await service.preview(
            template_version_id=version_id,
            variables={},
            user_id=owner_id,
        )

        assert engine.render_calls[0]["total_con_iva"] == ""

    async def test_negative_source_for_number_to_words_raises(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FUNCTION_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        with pytest.raises(ComputedVariableError):
            await service.preview(
                template_version_id=version_id,
                variables={"monto": "-1"},
                user_id=owner_id,
            )


class TestBulkExcelExcludesComputedVariables:
    """Computed variables are server-resolved, never user-supplied — they
    must be excluded from bulk Excel column headers AND from the expected
    header set used to validate an uploaded file."""

    async def test_excel_template_omits_computed_columns(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        excel_bytes, _filename = await service.generate_excel_template(version_id)

        wb = openpyxl.load_workbook(BytesIO(excel_bytes))
        headers = [cell.value for cell in wb.active[1] if cell.value is not None]
        assert headers == ["monto"]
        assert "total_con_iva" not in headers

    async def test_parse_excel_data_does_not_require_computed_column(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FORMULA_META
        )
        service = make_service(fake_template_repo, fake_storage, engine)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["monto"])
        ws.append(["400.00"])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        rows = await service.parse_excel_data(version_id, buf.read())
        assert rows == [{"monto": "400.00"}]


class TestGenerateBulkResolvesComputed:
    """generate_bulk() must resolve computed variables per row — same
    server-authoritative rule as generate_single()/preview() — and a
    ComputedVariableError raised mid-batch must roll back every file
    already uploaded for prior rows (mirrors the PdfConversionError bulk
    rollback contract in TestGenerateBulkDualFormat)."""

    async def test_engine_called_with_resolved_dicts_per_row(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FUNCTION_META
        )
        service = make_service(
            fake_template_repo, fake_storage, engine, doc_repo=FakeDocumentRepository()
        )

        rows = [
            {"monto": "400.00"},
            {"monto": "1500.50"},
        ]
        await service.generate_bulk(
            template_version_id=version_id,
            rows=rows,
            tenant_id=tenant_id,
            created_by=owner_id,
        )

        assert len(engine.render_calls) == 2
        assert engine.render_calls[0]["monto_en_letras"] == "CUATROCIENTOS 00/100"
        assert engine.render_calls[1]["monto_en_letras"] == "UN MIL QUINIENTOS 50/100"

    async def test_row_computed_error_rolls_back_prior_uploads(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        """Row 2 has a negative source for number_to_words (out of domain),
        which resolve_computed raises as ComputedVariableError. All files
        already uploaded for row 1 (DOCX+PDF) must be deleted, and no
        Document rows persisted."""
        engine = RecordingTemplateEngine()
        version, version_id, tenant_id, owner_id = seed_version_with_computed(
            fake_template_repo, fake_storage, FUNCTION_META
        )
        doc_repo = FakeDocumentRepository()
        service = make_service(
            fake_template_repo,
            fake_storage,
            engine,
            doc_repo=doc_repo,
            pdf_converter=FakePdfConverter(),
        )

        rows = [
            {"monto": "400.00"},
            {"monto": "-5"},
        ]

        with pytest.raises(ComputedVariableError):
            await service.generate_bulk(
                template_version_id=version_id,
                rows=rows,
                tenant_id=tenant_id,
                created_by=owner_id,
            )

        doc_files = [(b, p) for (b, p) in fake_storage.files if b == "documents"]
        assert len(doc_files) == 0, (
            f"Expected all bulk files deleted after rollback, but found: {[p for (_, p) in doc_files]}"
        )
        assert len(doc_repo._documents) == 0
