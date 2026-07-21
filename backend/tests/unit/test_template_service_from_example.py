"""Unit tests for TemplateService.analyze_example / create_template_from_example.

Uses FakeTemplateEngine's string-level document model: docx bytes are plain
UTF-8 text; apply_variable_mappings replaces literals with {{ placeholders }}
and extract_variables scans the bytes for {{ ... }} markers.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.application.services.template_service import TemplateService
from app.domain.exceptions import (
    DomainError,
    MappingTextNotFoundError,
    QuotaExceededError,
)
from tests.fakes import (
    FakeQuotaService,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


EXAMPLE_BYTES = "Contrato entre JUAN PEREZ y ACME SRL en La Paz.".encode("utf-8")
MAPPINGS = [
    {"text": "JUAN PEREZ", "variable": "client_name"},
    {"text": "ACME SRL", "variable": "company"},
]
REWRITTEN_BYTES = "Contrato entre {{ client_name }} y {{ company }} en La Paz.".encode(
    "utf-8"
)


def make_service(
    fake_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    fake_engine: FakeTemplateEngine,
    quota_service=None,
    tier_id=None,
) -> TemplateService:
    return TemplateService(
        repository=fake_repo,
        storage=fake_storage,
        engine=fake_engine,
        quota_service=quota_service,
        tier_id=tier_id,
    )


class TestAnalyzeExample:
    async def test_returns_engine_structure_without_storing(
        self, fake_template_repo, fake_storage, fake_template_engine
    ):
        structure = {
            "headers": [],
            "body": [
                {
                    "kind": "paragraph",
                    "level": 0,
                    "spans": [{"text": "Contrato entre JUAN PEREZ", "variable": None}],
                }
            ],
            "footers": [],
        }
        fake_template_engine.structure_to_return = structure
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        result = await service.analyze_example(EXAMPLE_BYTES)

        assert result == structure
        # No side effects: nothing stored, nothing created
        assert fake_storage.files == {}
        assert fake_template_repo._templates == {}


class TestCreateTemplateFromExample:
    async def test_happy_path_stores_rewritten_bytes_and_mapped_variables(
        self, fake_template_repo, fake_storage, fake_template_engine
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        template = await service.create_template_from_example(
            name="Contrato desde ejemplo",
            file_bytes=EXAMPLE_BYTES,
            mappings=MAPPINGS,
            tenant_id=tenant_id,
            created_by=user_id,
            description="creado desde un documento real",
        )

        # Template created exactly like the standard upload pipeline
        assert template.name == "Contrato desde ejemplo"
        assert template.current_version == 1
        assert len(template.versions) == 1

        # Variables come from EXTRACTION over the rewritten docx = mapped set
        assert set(template.versions[0].variables) == {"client_name", "company"}

        # The bytes stored at v1 are the REWRITTEN ones, not the original
        path = f"{tenant_id}/{template.id}/v1/template.docx"
        assert fake_storage.files[("templates", path)] == REWRITTEN_BYTES

    async def test_quota_enforced_before_creation(
        self, fake_template_repo, fake_storage, fake_template_engine
    ):
        service = make_service(
            fake_template_repo,
            fake_storage,
            fake_template_engine,
            quota_service=FakeQuotaService(exceeded_resource="max_templates"),
            tier_id=uuid.uuid4(),
        )

        with pytest.raises(QuotaExceededError):
            await service.create_template_from_example(
                name="Bloqueada por cuota",
                file_bytes=EXAMPLE_BYTES,
                mappings=MAPPINGS,
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )

        assert fake_storage.files == {}
        assert fake_template_repo._templates == {}

    async def test_name_collision_raises_same_domain_error_as_upload(
        self, fake_template_repo, fake_storage, fake_template_engine, monkeypatch
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        async def _raise_integrity(**kwargs):
            raise IntegrityError("duplicate key", params=None, orig=Exception("dup"))

        monkeypatch.setattr(
            fake_template_repo, "create_template_with_version", _raise_integrity
        )

        with pytest.raises(DomainError) as exc_info:
            await service.create_template_from_example(
                name="Nombre repetido",
                file_bytes=EXAMPLE_BYTES,
                mappings=MAPPINGS,
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )

        assert "Ya existe una plantilla" in str(exc_info.value)

    async def test_missing_text_error_propagates_with_missing_list(
        self, fake_template_repo, fake_storage, fake_template_engine
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        with pytest.raises(MappingTextNotFoundError) as exc_info:
            await service.create_template_from_example(
                name="Con textos faltantes",
                file_bytes=EXAMPLE_BYTES,
                mappings=[
                    {"text": "NO EXISTE", "variable": "uno"},
                    {"text": "JUAN PEREZ", "variable": "client_name"},
                    {"text": "TAMPOCO", "variable": "dos"},
                ],
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )

        assert exc_info.value.missing_texts == ["NO EXISTE", "TAMPOCO"]
        # Nothing was stored or created
        assert fake_storage.files == {}
        assert fake_template_repo._templates == {}
