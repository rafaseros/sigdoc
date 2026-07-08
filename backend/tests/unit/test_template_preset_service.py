"""Unit tests for TemplatePresetService.

Access rule for ALL preset operations: template ACCESS (owner, shared-with-
user, or admin) — the same rule as GET /templates/{id}. Presets are shared
by everyone with access to the template (both creators and document
generators manage them — explicit product decision), unlike folders which
are strictly owner-scoped.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.template_preset_service import TemplatePresetService
from app.domain.entities import AuditAction, Template, TemplateVersion
from app.domain.exceptions import (
    DomainError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
    TemplatePresetNotFoundError,
)
from tests.fakes import (
    FakeAuditRepository,
    FakeTemplatePresetRepository,
    FakeTemplateRepository,
)


def make_service(
    fake_preset_repo: FakeTemplatePresetRepository,
    fake_template_repo: FakeTemplateRepository,
    audit_service: AuditService | None = None,
) -> TemplatePresetService:
    return TemplatePresetService(
        preset_repository=fake_preset_repo,
        template_repository=fake_template_repo,
        audit_service=audit_service,
    )


def seed_template(
    fake_template_repo: FakeTemplateRepository,
    owner_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed a bare template. Returns (template_id, tenant_id, owner_id)."""
    tenant_uuid = tenant_id if tenant_id is not None else uuid.uuid4()
    owner_uuid = owner_id if owner_id is not None else uuid.uuid4()
    template_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    template = Template(
        id=template_id,
        tenant_id=tenant_uuid,
        name="Preset Test Template",
        description=None,
        current_version=1,
        created_by=owner_uuid,
        versions=[],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    return template_id, tenant_uuid, owner_uuid


# ---------------------------------------------------------------------------
# list_presets
# ---------------------------------------------------------------------------


class TestListPresets:
    async def test_owner_can_list_presets_ordered_by_name(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Zeta",
            values={"a": "1"},
        )
        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Alpha",
            values={"b": "2"},
        )

        presets = await service.list_presets(template_id, user_id=owner_id, role="template_creator")
        assert [p.name for p in presets] == ["Alpha", "Zeta"]

    async def test_shared_user_can_list_presets(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        recipient_id = uuid.uuid4()
        await fake_template_repo.add_share(
            template_id=template_id, user_id=recipient_id, tenant_id=tenant_id, shared_by=owner_id
        )

        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Cliente Frecuente",
            values={"a": "1"},
        )

        presets = await service.list_presets(
            template_id, user_id=recipient_id, role="document_generator"
        )
        assert len(presets) == 1

    async def test_unrelated_user_is_denied(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        stranger_id = uuid.uuid4()

        with pytest.raises(TemplateAccessDeniedError):
            await service.list_presets(template_id, user_id=stranger_id, role="document_generator")

    async def test_admin_can_list_presets_without_access(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        admin_id = uuid.uuid4()

        presets = await service.list_presets(template_id, user_id=admin_id, role="admin")
        assert presets == []

    async def test_unknown_template_raises_not_found(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        with pytest.raises(TemplateNotFoundError):
            await service.list_presets(uuid.uuid4(), user_id=uuid.uuid4(), role="admin")


# ---------------------------------------------------------------------------
# create_preset
# ---------------------------------------------------------------------------


class TestCreatePreset:
    async def test_owner_can_create_preset(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Cliente A",
            values={"nombre": "Acme"},
        )
        assert preset.name == "Cliente A"
        assert preset.values == {"nombre": "Acme"}
        assert preset.created_by == owner_id

    async def test_shared_user_can_create_preset(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        """Explicit product decision: both creators and document
        generators can manage presets on a template they have access to."""
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        recipient_id = uuid.uuid4()
        await fake_template_repo.add_share(
            template_id=template_id, user_id=recipient_id, tenant_id=tenant_id, shared_by=owner_id
        )

        preset = await service.create_preset(
            template_id=template_id,
            user_id=recipient_id,
            role="document_generator",
            tenant_id=tenant_id,
            name="Cliente B",
            values={"nombre": "Beta"},
        )
        assert preset.created_by == recipient_id

    async def test_unrelated_user_is_denied(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        stranger_id = uuid.uuid4()

        with pytest.raises(TemplateAccessDeniedError):
            await service.create_preset(
                template_id=template_id,
                user_id=stranger_id,
                role="document_generator",
                tenant_id=tenant_id,
                name="Cliente C",
                values={},
            )

    async def test_duplicate_name_for_same_template_raises_domain_error(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Duplicado",
            values={},
        )
        with pytest.raises(DomainError):
            await service.create_preset(
                template_id=template_id,
                user_id=owner_id,
                role="template_creator",
                tenant_id=tenant_id,
                name="Duplicado",
                values={},
            )

    async def test_same_name_allowed_across_different_templates(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id_1, tenant_id, owner_id = seed_template(fake_template_repo)
        template_id_2, _, _ = seed_template(fake_template_repo, owner_id=owner_id, tenant_id=tenant_id)

        await service.create_preset(
            template_id=template_id_1,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Compartido",
            values={},
        )
        preset2 = await service.create_preset(
            template_id=template_id_2,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Compartido",
            values={},
        )
        assert preset2.name == "Compartido"

    async def test_create_logs_audit_event(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        audit_service = AuditService(audit_repo=fake_audit_repo)
        service = make_service(fake_template_preset_repo, fake_template_repo, audit_service)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Auditado",
            values={},
        )

        import asyncio
        await asyncio.sleep(0)  # let the fire-and-forget audit task run
        logged = [e for e in fake_audit_repo._entries if e.action == AuditAction.PRESET_CREATE]
        assert len(logged) == 1


# ---------------------------------------------------------------------------
# update_preset
# ---------------------------------------------------------------------------


class TestUpdatePreset:
    async def test_owner_can_rename_and_update_values(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Original",
            values={"a": "1"},
        )

        updated = await service.update_preset(
            template_id=template_id,
            preset_id=preset.id,
            user_id=owner_id,
            role="template_creator",
            name="Renombrado",
            name_provided=True,
            values={"a": "2"},
            values_provided=True,
        )
        assert updated.name == "Renombrado"
        assert updated.values == {"a": "2"}

    async def test_shared_user_can_update_preset(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        recipient_id = uuid.uuid4()
        await fake_template_repo.add_share(
            template_id=template_id, user_id=recipient_id, tenant_id=tenant_id, shared_by=owner_id
        )
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Original",
            values={},
        )

        updated = await service.update_preset(
            template_id=template_id,
            preset_id=preset.id,
            user_id=recipient_id,
            role="document_generator",
            values={"x": "y"},
            values_provided=True,
        )
        assert updated.values == {"x": "y"}
        assert updated.name == "Original"  # not provided -> unchanged

    async def test_unrelated_user_is_denied(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Original",
            values={},
        )
        stranger_id = uuid.uuid4()

        with pytest.raises(TemplateAccessDeniedError):
            await service.update_preset(
                template_id=template_id,
                preset_id=preset.id,
                user_id=stranger_id,
                role="document_generator",
                name="Hack",
                name_provided=True,
            )

    async def test_unknown_preset_id_raises_not_found(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        with pytest.raises(TemplatePresetNotFoundError):
            await service.update_preset(
                template_id=template_id,
                preset_id=uuid.uuid4(),
                user_id=owner_id,
                role="template_creator",
                name="X",
                name_provided=True,
            )

    async def test_preset_from_foreign_template_raises_not_found(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        """A preset_id that exists but belongs to a DIFFERENT template must
        404 non-leaking — same as if it didn't exist at all."""
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id_1, tenant_id, owner_id = seed_template(fake_template_repo)
        template_id_2, _, _ = seed_template(fake_template_repo, owner_id=owner_id, tenant_id=tenant_id)

        preset = await service.create_preset(
            template_id=template_id_1,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Original",
            values={},
        )

        with pytest.raises(TemplatePresetNotFoundError):
            await service.update_preset(
                template_id=template_id_2,
                preset_id=preset.id,
                user_id=owner_id,
                role="template_creator",
                name="X",
                name_provided=True,
            )

    async def test_rename_to_duplicate_name_raises_domain_error(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Existente",
            values={},
        )
        preset2 = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Otro",
            values={},
        )

        with pytest.raises(DomainError):
            await service.update_preset(
                template_id=template_id,
                preset_id=preset2.id,
                user_id=owner_id,
                role="template_creator",
                name="Existente",
                name_provided=True,
            )


# ---------------------------------------------------------------------------
# delete_preset
# ---------------------------------------------------------------------------


class TestDeletePreset:
    async def test_owner_can_delete_preset(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Borrame",
            values={},
        )

        await service.delete_preset(
            template_id=template_id, preset_id=preset.id, user_id=owner_id, role="template_creator"
        )
        assert await fake_template_preset_repo.get_by_id(preset.id) is None

    async def test_shared_user_can_delete_preset(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        recipient_id = uuid.uuid4()
        await fake_template_repo.add_share(
            template_id=template_id, user_id=recipient_id, tenant_id=tenant_id, shared_by=owner_id
        )
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Borrame",
            values={},
        )

        await service.delete_preset(
            template_id=template_id, preset_id=preset.id, user_id=recipient_id, role="document_generator"
        )
        assert await fake_template_preset_repo.get_by_id(preset.id) is None

    async def test_unrelated_user_is_denied(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)
        preset = await service.create_preset(
            template_id=template_id,
            user_id=owner_id,
            role="template_creator",
            tenant_id=tenant_id,
            name="Persiste",
            values={},
        )
        stranger_id = uuid.uuid4()

        with pytest.raises(TemplateAccessDeniedError):
            await service.delete_preset(
                template_id=template_id, preset_id=preset.id, user_id=stranger_id, role="document_generator"
            )
        assert await fake_template_preset_repo.get_by_id(preset.id) is not None

    async def test_unknown_preset_id_raises_not_found(
        self,
        fake_template_preset_repo: FakeTemplatePresetRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        service = make_service(fake_template_preset_repo, fake_template_repo)
        template_id, tenant_id, owner_id = seed_template(fake_template_repo)

        with pytest.raises(TemplatePresetNotFoundError):
            await service.delete_preset(
                template_id=template_id, preset_id=uuid.uuid4(), user_id=owner_id, role="template_creator"
            )
