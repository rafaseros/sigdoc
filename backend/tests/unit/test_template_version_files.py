"""Unit tests for related documents per template version (Tanda 3).

Covers TemplateService.attach_version_file / detach_version_file /
download_version_file, get_version_structure(file_id=...) and the
carry-forward of related files on upload_new_version.

Strict TDD: written first (RED), then the service/repo/entity layer is
implemented (GREEN).
"""
from __future__ import annotations

import uuid

import pytest

from app.application.services.template_service import TemplateService
from app.domain.entities import TemplateVersionFile
from app.domain.exceptions import (
    DomainError,
    TemplateAccessDeniedError,
    TemplateVersionFileNotFoundError,
    TemplateVersionNotFoundError,
)
from tests.fakes import (
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PRIMARY_BYTES = b"Hello {{ name }} and {{ company }}"
RECIBO_BYTES = b"Recibo for {{ name }} amount {{ monto }}"
FACTURA_BYTES = b"Factura {{ fecha }}"


class RecordingEngine(FakeTemplateEngine):
    """FakeTemplateEngine that records extract_structure input bytes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.structure_calls: list[bytes] = []

    async def extract_structure(self, file_bytes: bytes) -> dict:
        self.structure_calls.append(file_bytes)
        return await super().extract_structure(file_bytes)


def make_service(
    repo: FakeTemplateRepository,
    storage: FakeStorageService,
    engine: FakeTemplateEngine,
) -> TemplateService:
    return TemplateService(repository=repo, storage=storage, engine=engine)


async def upload_primary(
    service: TemplateService,
    *,
    name: str = "Contrato Marco",
) -> tuple:
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
    version = template.versions[0]
    return template, version, tenant_id, owner_id


# ---------------------------------------------------------------------------
# attach_version_file
# ---------------------------------------------------------------------------


class TestAttachVersionFile:
    async def test_happy_path_creates_row_and_uploads_bytes(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, tenant_id, owner_id = await upload_primary(service)

        file = await service.attach_version_file(
            template.id,
            version.id,
            label="  Recibo de pago  ",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        assert file.label == "Recibo de pago"  # trimmed
        assert file.variables == ["name", "monto"]
        assert file.position == 0
        expected_key = f"{tenant_id}/{template.id}/v1/files/{file.id}.docx"
        assert fake_storage.files[("templates", expected_key)] == RECIBO_BYTES
        assert file.minio_path == expected_key

        stored = await fake_template_repo.get_version_file(version.id, file.id)
        assert stored is not None
        assert stored.label == "Recibo de pago"

    async def test_happy_path_unions_version_variables_and_meta(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        # Simulate a user-configured meta entry BEFORE attaching
        version.variables_meta[1]["type"] = "decimal"

        await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo de pago",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        refreshed = await fake_template_repo.get_version_by_id(version.id)
        # Existing names first (original order), genuinely new names appended
        assert refreshed.variables == ["name", "company", "monto"]
        meta_names = [m["name"] for m in refreshed.variables_meta]
        assert meta_names == ["name", "company", "monto"]
        # Existing entries kept as-is (user config preserved)
        assert refreshed.variables_meta[1]["type"] == "decimal"
        # New entry mirrors the engine-produced default entry
        assert refreshed.variables_meta[2]["contexts"] == ["context for monto"]

    async def test_second_file_gets_next_position(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        first = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )
        second = await service.attach_version_file(
            template.id,
            version.id,
            label="Factura",
            file_bytes=FACTURA_BYTES,
            file_size=len(FACTURA_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        assert first.position == 0
        assert second.position == 1

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
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        with pytest.raises(DomainError) as exc_info:
            await service.attach_version_file(
                template.id,
                version.id,
                label="  Recibo de pago ",
                file_bytes=FACTURA_BYTES,
                file_size=len(FACTURA_BYTES),
                user_id=owner_id,
                role="template_creator",
            )
        assert "etiqueta" in str(exc_info.value).lower()

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
            await service.attach_version_file(
                template.id,
                v1.id,
                label="Recibo",
                file_bytes=RECIBO_BYTES,
                file_size=len(RECIBO_BYTES),
                user_id=owner_id,
                role="template_creator",
            )
        assert "vigente" in str(exc_info.value).lower()

    async def test_non_owner_is_denied(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, _owner_id = await upload_primary(service)

        with pytest.raises(TemplateAccessDeniedError):
            await service.attach_version_file(
                template.id,
                version.id,
                label="Recibo",
                file_bytes=RECIBO_BYTES,
                file_size=len(RECIBO_BYTES),
                user_id=str(uuid.uuid4()),
                role="user",
            )

    async def test_admin_can_attach(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, _owner_id = await upload_primary(service)

        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=str(uuid.uuid4()),
            role="admin",
        )
        assert file.label == "Recibo"

    async def test_version_of_another_template_raises_404(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template_a, _version_a, _, owner_id = await upload_primary(service, name="A")
        _template_b, version_b, _, _ = await upload_primary(service, name="B")

        with pytest.raises(TemplateVersionNotFoundError):
            await service.attach_version_file(
                template_a.id,
                version_b.id,
                label="Recibo",
                file_bytes=RECIBO_BYTES,
                file_size=len(RECIBO_BYTES),
                user_id=owner_id,
                role="admin",
            )

    async def test_duplicate_label_race_translates_integrity_error_to_domain_error(
        self,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Concurrent attaches with the same label pass the app-level check
        and the loser hits uq_template_version_files_version_label — the
        service must surface the SAME duplicate-label DomainError (mapped to
        409 by the endpoint), never a raw IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        class RacingRepo(FakeTemplateRepository):
            async def add_version_file(self, file):
                raise IntegrityError(
                    "INSERT INTO template_version_files ...",
                    {},
                    Exception(
                        "duplicate key value violates unique constraint "
                        '"uq_template_version_files_version_label"'
                    ),
                )

        repo = RacingRepo()
        service = make_service(repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        with pytest.raises(DomainError) as exc_info:
            await service.attach_version_file(
                template.id,
                version.id,
                label="Recibo de pago",
                file_bytes=RECIBO_BYTES,
                file_size=len(RECIBO_BYTES),
                user_id=owner_id,
                role="template_creator",
            )

        assert not isinstance(exc_info.value, IntegrityError)
        assert "etiqueta" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# detach_version_file
# ---------------------------------------------------------------------------


class TestDetachVersionFile:
    async def test_detach_removes_row_and_storage_object(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        await service.detach_version_file(
            template.id, version.id, file.id, user_id=owner_id, role="template_creator"
        )

        assert await fake_template_repo.get_version_file(version.id, file.id) is None
        assert ("templates", file.minio_path) not in fake_storage.files

    async def test_detach_recomputes_union_including_primary_reextraction(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        recibo = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )
        await service.attach_version_file(
            template.id,
            version.id,
            label="Factura",
            file_bytes=FACTURA_BYTES,
            file_size=len(FACTURA_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        # user-configured meta on a surviving name must be preserved
        refreshed = await fake_template_repo.get_version_by_id(version.id)
        for entry in refreshed.variables_meta:
            if entry["name"] == "company":
                entry["type"] = "select"
                entry["options"] = ["A", "B"]

        await service.detach_version_file(
            template.id, version.id, recibo.id, user_id=owner_id, role="template_creator"
        )

        refreshed = await fake_template_repo.get_version_by_id(version.id)
        # monto came only from the detached file → gone; fecha survives
        assert refreshed.variables == ["name", "company", "fecha"]
        meta_by_name = {m["name"]: m for m in refreshed.variables_meta}
        assert set(meta_by_name) == {"name", "company", "fecha"}
        assert meta_by_name["company"]["type"] == "select"
        assert meta_by_name["company"]["options"] == ["A", "B"]

    async def test_detach_unknown_file_raises_404(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        with pytest.raises(TemplateVersionFileNotFoundError):
            await service.detach_version_file(
                template.id,
                version.id,
                uuid.uuid4(),
                user_id=owner_id,
                role="template_creator",
            )

    async def test_detach_non_owner_is_denied(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service.detach_version_file(
                template.id, version.id, file.id, user_id=str(uuid.uuid4()), role="user"
            )


class FlakyStorage(FakeStorageService):
    """FakeStorageService with per-path failure injection + delete recording."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_download_paths: set[str] = set()
        self.fail_delete_paths: set[str] = set()
        self.delete_calls: list[tuple[str, str]] = []

    async def download_file(self, bucket: str, path: str) -> bytes:
        if path in self.fail_download_paths:
            raise RuntimeError(f"storage down for {path}")
        return await super().download_file(bucket, path)

    async def delete_file(self, bucket: str, path: str) -> None:
        self.delete_calls.append((bucket, path))
        if path in self.fail_delete_paths:
            raise RuntimeError(f"delete failed for {path}")
        await super().delete_file(bucket, path)


class TestDetachOrderingSafety:
    """detach_version_file must do ALL fallible storage/engine work (primary
    download + variables recompute) BEFORE deleting anything, and delete the
    MinIO object LAST (best-effort) — a recompute failure must leave both the
    row and the object intact."""

    async def test_recompute_failure_leaves_row_and_object_intact(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_template_engine: FakeTemplateEngine,
    ):
        storage = FlakyStorage()
        service = make_service(fake_template_repo, storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        # Primary download fails during the union recompute
        storage.fail_download_paths.add(version.minio_path)

        with pytest.raises(RuntimeError):
            await service.detach_version_file(
                template.id,
                version.id,
                file.id,
                user_id=owner_id,
                role="template_creator",
            )

        # Clean abort: row still present, object still present, and the
        # detached object was NEVER deleted from storage.
        assert (
            await fake_template_repo.get_version_file(version.id, file.id)
            is not None
        )
        assert ("templates", file.minio_path) in storage.files
        assert ("templates", file.minio_path) not in storage.delete_calls

    async def test_minio_delete_failure_still_detaches_and_recomputes(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_template_engine: FakeTemplateEngine,
    ):
        storage = FlakyStorage()
        service = make_service(fake_template_repo, storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        storage.fail_delete_paths.add(file.minio_path)

        await service.detach_version_file(
            template.id, version.id, file.id, user_id=owner_id, role="template_creator"
        )

        # Row gone, union recomputed (monto came only from the detached file),
        # only a harmless orphaned object remains in storage.
        assert await fake_template_repo.get_version_file(version.id, file.id) is None
        refreshed = await fake_template_repo.get_version_by_id(version.id)
        assert refreshed.variables == ["name", "company"]
        assert ("templates", file.minio_path) in storage.delete_calls
        assert ("templates", file.minio_path) in storage.files  # orphan


# ---------------------------------------------------------------------------
# download_version_file
# ---------------------------------------------------------------------------


class TestDownloadVersionFile:
    async def test_owner_downloads_bytes_and_filename(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service, name="Contrato Marco")
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo de pago",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        file_bytes, filename = await service.download_version_file(
            template.id, version.id, file.id, user_id=owner_id, role="template_creator"
        )

        assert file_bytes == RECIBO_BYTES
        assert filename == "Contrato Marco_Recibo de pago_v1.docx"

    async def test_shared_user_can_download(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, tenant_id, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        shared_user = uuid.uuid4()
        await fake_template_repo.add_share(
            template_id=template.id,
            user_id=shared_user,
            tenant_id=uuid.UUID(tenant_id),
            shared_by=uuid.UUID(owner_id),
        )

        file_bytes, _ = await service.download_version_file(
            template.id, version.id, file.id, user_id=str(shared_user), role="user"
        )
        assert file_bytes == RECIBO_BYTES

    async def test_unrelated_user_is_denied(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service.download_version_file(
                template.id, version.id, file.id, user_id=str(uuid.uuid4()), role="user"
            )

    async def test_wrong_version_raises_404(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, tenant_id, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        # v2 exists, but the file belongs to v1 → looking it up under v2 is 404
        result = await service.upload_new_version(
            template_id=str(template.id),
            file_bytes=PRIMARY_BYTES,
            file_size=len(PRIMARY_BYTES),
            tenant_id=tenant_id,
            user_id=owner_id,
            role="template_creator",
        )
        v2 = next(
            v for v in result["template"].versions if v.version == result["new_version"]
        )

        # The carried-forward copy has a NEW id — the OLD file id must 404 under v2
        with pytest.raises(TemplateVersionFileNotFoundError):
            await service.download_version_file(
                template.id, v2.id, file.id, user_id=owner_id, role="template_creator"
            )


# ---------------------------------------------------------------------------
# get_version_structure with file_id
# ---------------------------------------------------------------------------


class TestVersionStructureFileId:
    async def test_structure_of_related_file_uses_file_bytes(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingEngine()
        service = make_service(fake_template_repo, fake_storage, engine)
        template, version, _, owner_id = await upload_primary(service)
        file = await service.attach_version_file(
            template.id,
            version.id,
            label="Recibo",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        structure = await service.get_version_structure(
            template.id,
            version.id,
            user_id=owner_id,
            role="template_creator",
            file_id=file.id,
        )

        assert structure == {"headers": [], "body": [], "footers": []}
        assert engine.structure_calls[-1] == RECIBO_BYTES

    async def test_structure_unknown_file_id_raises_404(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, version, _, owner_id = await upload_primary(service)

        with pytest.raises(TemplateVersionFileNotFoundError):
            await service.get_version_structure(
                template.id,
                version.id,
                user_id=owner_id,
                role="template_creator",
                file_id=uuid.uuid4(),
            )

    async def test_structure_without_file_id_uses_primary(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
    ):
        engine = RecordingEngine()
        service = make_service(fake_template_repo, fake_storage, engine)
        template, version, _, owner_id = await upload_primary(service)

        await service.get_version_structure(
            template.id, version.id, user_id=owner_id, role="template_creator"
        )
        assert engine.structure_calls[-1] == PRIMARY_BYTES


# ---------------------------------------------------------------------------
# upload_new_version carries related files forward
# ---------------------------------------------------------------------------


class TestCarryForwardOnNewVersion:
    async def test_files_copied_with_new_ids_and_union_meta(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, v1, tenant_id, owner_id = await upload_primary(service)

        old_file = await service.attach_version_file(
            template.id,
            v1.id,
            label="Recibo de pago",
            file_bytes=RECIBO_BYTES,
            file_size=len(RECIBO_BYTES),
            user_id=owner_id,
            role="template_creator",
        )

        # user-configures the meta of a carried variable on v1
        v1_refreshed = await fake_template_repo.get_version_by_id(v1.id)
        for entry in v1_refreshed.variables_meta:
            if entry["name"] == "monto":
                entry["type"] = "decimal"

        # New primary for v2 only has {{ name }}
        result = await service.upload_new_version(
            template_id=str(template.id),
            file_bytes=b"V2 body {{ name }}",
            file_size=18,
            tenant_id=tenant_id,
            user_id=owner_id,
            role="template_creator",
        )

        assert result["new_version"] == 2
        v2 = next(
            v for v in result["template"].versions if v.version == 2
        )

        # Related file carried forward with a NEW id, same label/vars/position
        assert len(v2.files) == 1
        carried = v2.files[0]
        assert carried.id != old_file.id
        assert carried.label == "Recibo de pago"
        assert carried.variables == ["name", "monto"]
        assert carried.position == 0
        assert carried.file_size == old_file.file_size

        # Bytes copied to the new version's files/ key
        new_key = f"{tenant_id}/{template.id}/v2/files/{carried.id}.docx"
        assert fake_storage.files[("templates", new_key)] == RECIBO_BYTES

        # Union: v2 primary extraction (name) + carried file vars (monto)
        assert result["variables"] == ["name", "monto"]
        assert v2.variables == ["name", "monto"]

        # meta preserved for surviving user-configured names
        meta_by_name = {m["name"]: m for m in v2.variables_meta}
        assert set(meta_by_name) == {"name", "monto"}
        assert meta_by_name["monto"]["type"] == "decimal"

    async def test_no_files_keeps_existing_behavior(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        template, _v1, tenant_id, owner_id = await upload_primary(service)

        result = await service.upload_new_version(
            template_id=str(template.id),
            file_bytes=b"V2 body {{ name }}",
            file_size=18,
            tenant_id=tenant_id,
            user_id=owner_id,
            role="template_creator",
        )

        assert result["variables"] == ["name"]
        v2 = next(v for v in result["template"].versions if v.version == 2)
        assert v2.files == []
