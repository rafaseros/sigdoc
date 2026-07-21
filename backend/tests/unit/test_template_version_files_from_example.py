"""Unit tests for TemplateService.attach_version_file_from_example.

The attach-from-example flow rewrites a filled example .docx (literal texts →
{{ placeholders }}, same engine contract as create_template_from_example) and
then delegates to the EXISTING attach pipeline — same gates, same variables
union, same audit. Uses FakeTemplateEngine's string-level document model.

Strict TDD: written first (RED), then the service method is implemented
(GREEN).
"""
from __future__ import annotations

import uuid

import pytest

from app.application.services.template_service import TemplateService
from app.domain.exceptions import (
    DomainError,
    InvalidVariableMappingError,
    MappingTextNotFoundError,
    TemplateAccessDeniedError,
)
from tests.fakes import (
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


PRIMARY_BYTES = b"Hello {{ name }} and {{ company }}"
EXAMPLE_BYTES = "Recibo de JUAN PEREZ por 100 Bs.".encode("utf-8")
MAPPINGS = [
    {"text": "JUAN PEREZ", "variable": "name"},  # REUSES the version's variable
    {"text": "100", "variable": "monto"},  # genuinely new variable
]
REWRITTEN_BYTES = "Recibo de {{ name }} por {{ monto }} Bs.".encode("utf-8")


def make_service(
    repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
) -> TemplateService:
    return TemplateService(repository=repo, storage=storage, engine=engine)


async def upload_primary(service: TemplateService, *, name: str = "Contrato Marco"):
    """Upload a template whose primary docx carries {{ name }} / {{ company }}.

    Returns (template, version, tenant_id_str, owner_id_str).
    """
    tenant_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    template = await service.upload_template(
        name=name,
        file_bytes=PRIMARY_BYTES,
        file_size=len(PRIMARY_BYTES),
        tenant_id=tenant_id,
        created_by=owner_id,
    )
    return template, template.versions[0], tenant_id, owner_id


class TestAttachVersionFileFromExample:
    async def test_happy_path_stores_rewritten_bytes_with_mapped_variables(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, tenant_id, owner_id = await upload_primary(service)

        file = await service.attach_version_file_from_example(
            template.id,
            version.id,
            label="  Recibo de pago  ",
            file_bytes=EXAMPLE_BYTES,
            mappings=MAPPINGS,
            user_id=owner_id,
            role="template_creator",
        )

        # Same attach pipeline: trimmed label, position, per-file variables
        assert file.label == "Recibo de pago"
        assert file.variables == ["name", "monto"]
        assert file.position == 0
        assert file.file_size == len(REWRITTEN_BYTES)

        # The bytes stored for the related file are the REWRITTEN ones —
        # placeholders in, literals out.
        expected_key = f"{tenant_id}/{template.id}/v1/files/{file.id}.docx"
        stored = fake_storage.files[("templates", expected_key)]
        assert stored == REWRITTEN_BYTES
        stored_text = stored.decode("utf-8")
        assert "{{ name }}" in stored_text
        assert "{{ monto }}" in stored_text
        assert "JUAN PEREZ" not in stored_text

        row = await fake_template_repo.get_version_file(version.id, file.id)
        assert row is not None
        assert row.minio_path == expected_key

    async def test_existing_variable_reuse_keeps_union_and_meta_intact(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """CRITICAL: a mapping that reuses an existing variable name must NOT
        duplicate it in the version union and must preserve its existing
        (user-configured) variables_meta entry untouched."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        # Simulate a user-configured meta entry for "name" BEFORE attaching
        version.variables_meta[0]["type"] = "decimal"
        version.variables_meta[0]["help_text"] = "nombre completo"

        await service.attach_version_file_from_example(
            template.id,
            version.id,
            label="Recibo de pago",
            file_bytes=EXAMPLE_BYTES,
            mappings=MAPPINGS,
            user_id=owner_id,
            role="template_creator",
        )

        refreshed = await fake_template_repo.get_version_by_id(version.id)
        # "name" reused → NOT duplicated; only "monto" is appended.
        assert refreshed.variables == ["name", "company", "monto"]
        meta_names = [m["name"] for m in refreshed.variables_meta]
        assert meta_names == ["name", "company", "monto"]
        # Existing entry preserved exactly as configured
        assert refreshed.variables_meta[0]["type"] == "decimal"
        assert refreshed.variables_meta[0]["help_text"] == "nombre completo"
        # New entry mirrors the engine-produced default entry
        assert refreshed.variables_meta[2]["contexts"] == ["context for monto"]

    async def test_missing_text_error_propagates_and_stores_nothing(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)
        files_before = dict(fake_storage.files)

        with pytest.raises(MappingTextNotFoundError) as exc_info:
            await service.attach_version_file_from_example(
                template.id,
                version.id,
                label="Recibo de pago",
                file_bytes=EXAMPLE_BYTES,
                mappings=[
                    {"text": "NO EXISTE", "variable": "uno"},
                    {"text": "JUAN PEREZ", "variable": "name"},
                    {"text": "TAMPOCO", "variable": "dos"},
                ],
                user_id=owner_id,
                role="template_creator",
            )

        assert exc_info.value.missing_texts == ["NO EXISTE", "TAMPOCO"]
        # No object stored, no row created, union untouched
        assert fake_storage.files == files_before
        refreshed = await fake_template_repo.get_version_by_id(version.id)
        assert refreshed.variables == ["name", "company"]
        assert list(getattr(refreshed, "files", []) or []) == []

    async def test_invalid_variable_name_raises_mapping_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        with pytest.raises(InvalidVariableMappingError):
            await service.attach_version_file_from_example(
                template.id,
                version.id,
                label="Recibo",
                file_bytes=EXAMPLE_BYTES,
                mappings=[{"text": "JUAN PEREZ", "variable": "NombreCliente"}],
                user_id=owner_id,
                role="template_creator",
            )

    async def test_non_owner_is_denied_and_stores_nothing(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, _owner_id = await upload_primary(service)
        files_before = dict(fake_storage.files)

        with pytest.raises(TemplateAccessDeniedError):
            await service.attach_version_file_from_example(
                template.id,
                version.id,
                label="Recibo",
                file_bytes=EXAMPLE_BYTES,
                mappings=MAPPINGS,
                user_id=str(uuid.uuid4()),
                role="user",
            )

        assert fake_storage.files == files_before

    async def test_non_current_version_raises_domain_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, v1, tenant_id, owner_id = await upload_primary(service)

        # Create v2 so v1 is no longer current
        await service.upload_new_version(
            template_id=str(template.id),
            file_bytes=PRIMARY_BYTES,
            file_size=len(PRIMARY_BYTES),
            tenant_id=tenant_id,
            user_id=owner_id,
            role="template_creator",
        )

        with pytest.raises(DomainError) as exc_info:
            await service.attach_version_file_from_example(
                template.id,
                v1.id,
                label="Recibo",
                file_bytes=EXAMPLE_BYTES,
                mappings=MAPPINGS,
                user_id=owner_id,
                role="template_creator",
            )
        assert "vigente" in str(exc_info.value).lower()

    async def test_duplicate_label_raises_domain_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo de pago",
            file_bytes=b"Recibo {{ monto }}",
            file_size=18,
            user_id=owner_id,
            role="template_creator",
        )

        with pytest.raises(DomainError) as exc_info:
            await service.attach_version_file_from_example(
                template.id,
                version.id,
                label="  Recibo de pago ",
                file_bytes=EXAMPLE_BYTES,
                mappings=MAPPINGS,
                user_id=owner_id,
                role="template_creator",
            )
        assert "etiqueta" in str(exc_info.value).lower()

    async def test_admin_can_attach_from_example(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, _owner_id = await upload_primary(service)

        file = await service.attach_version_file_from_example(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=EXAMPLE_BYTES,
            mappings=MAPPINGS,
            user_id=str(uuid.uuid4()),
            role="admin",
        )
        assert file.label == "Recibo"
        assert file.variables == ["name", "monto"]
