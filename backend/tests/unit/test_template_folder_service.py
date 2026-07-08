"""Unit tests for TemplateFolderService — personal flat template folders."""
import uuid

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.template_folder_service import TemplateFolderService
from app.domain.exceptions import DomainError, TemplateFolderNotFoundError
from tests.fakes import FakeAuditRepository, FakeTemplateFolderRepository, FakeTemplateRepository


def make_service(
    fake_repo: FakeTemplateFolderRepository,
    audit_service: AuditService | None = None,
) -> TemplateFolderService:
    return TemplateFolderService(repository=fake_repo, audit_service=audit_service)


# ---------------------------------------------------------------------------
# create_folder
# ---------------------------------------------------------------------------


class TestCreateFolder:
    async def test_creates_folder_owned_by_caller(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="Contratos"
        )

        assert folder.name == "Contratos"
        assert folder.owner_id == owner_id
        assert folder.tenant_id == tenant_id
        assert len(fake_template_folder_repo._folders) == 1

    async def test_duplicate_name_for_same_owner_raises_domain_error(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Contratos")

        with pytest.raises(DomainError):
            await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Contratos")

    async def test_same_name_allowed_for_different_owners(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_a = uuid.uuid4()
        owner_b = uuid.uuid4()

        await service.create_folder(tenant_id=tenant_id, owner_id=owner_a, name="Contratos")
        folder_b = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_b, name="Contratos"
        )

        assert folder_b.name == "Contratos"
        assert len(fake_template_folder_repo._folders) == 2

    async def test_create_logs_audit(
        self,
        fake_template_folder_repo: FakeTemplateFolderRepository,
        fake_audit_repo: FakeAuditRepository,
    ):
        from app.domain.entities import AuditAction

        audit_service = AuditService(audit_repo=fake_audit_repo)
        service = make_service(fake_template_folder_repo, audit_service=audit_service)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="Auditada"
        )

        import asyncio

        await asyncio.sleep(0)  # let the fire-and-forget audit task run
        entries = [e for e in fake_audit_repo._entries if e.action == AuditAction.FOLDER_CREATE]
        assert len(entries) == 1
        assert entries[0].resource_id == folder.id


# ---------------------------------------------------------------------------
# list_folders
# ---------------------------------------------------------------------------


class TestListFolders:
    async def test_returns_only_owners_folders(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_a = uuid.uuid4()
        owner_b = uuid.uuid4()

        await service.create_folder(tenant_id=tenant_id, owner_id=owner_a, name="Mine")
        await service.create_folder(tenant_id=tenant_id, owner_id=owner_b, name="TheirsOnly")

        folders = await service.list_folders(owner_a)

        assert [f.name for f in folders] == ["Mine"]

    async def test_ordered_by_name(self, fake_template_folder_repo: FakeTemplateFolderRepository):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Zebra")
        await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Alpha")

        folders = await service.list_folders(owner_id)

        assert [f.name for f in folders] == ["Alpha", "Zebra"]

    async def test_includes_template_count(
        self,
        fake_template_folder_repo: FakeTemplateFolderRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        from datetime import datetime, timezone

        from app.domain.entities import Template

        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()

        folder = await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Con2")
        empty_folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="Con0"
        )

        now = datetime.now(timezone.utc)
        for i in range(2):
            tpl_id = uuid.uuid4()
            fake_template_repo._templates[tpl_id] = Template(
                id=tpl_id,
                tenant_id=tenant_id,
                name=f"Tpl{i}",
                created_by=owner_id,
                folder_id=folder.id,
                created_at=now,
                updated_at=now,
            )

        folders = await service.list_folders(owner_id)
        counts = {f.id: f.template_count for f in folders}

        assert counts[folder.id] == 2
        assert counts[empty_folder.id] == 0

    async def test_orphaned_folder_id_with_mismatched_owner_does_not_count(
        self,
        fake_template_folder_repo: FakeTemplateFolderRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        """Defense-in-depth: a template row with `folder_id=F` but
        `created_by != F.owner_id` must never inflate F's template_count.
        This guards against any future code path that leaves a template's
        `folder_id` pointing at a folder it no longer has an ownership
        relationship with."""
        from datetime import datetime, timezone

        from app.domain.entities import Template

        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="OrphanTarget"
        )

        now = datetime.now(timezone.utc)
        orphan_tpl_id = uuid.uuid4()
        fake_template_repo._templates[orphan_tpl_id] = Template(
            id=orphan_tpl_id,
            tenant_id=tenant_id,
            name="OrphanedTemplate",
            created_by=other_user_id,
            folder_id=folder.id,
            created_at=now,
            updated_at=now,
        )

        folders = await service.list_folders(owner_id)
        counts = {f.id: f.template_count for f in folders}

        assert counts[folder.id] == 0


# ---------------------------------------------------------------------------
# rename_folder
# ---------------------------------------------------------------------------


class TestRenameFolder:
    async def test_owner_can_rename(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        folder = await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Old")

        renamed = await service.rename_folder(folder.id, owner_id=owner_id, name="New")

        assert renamed.name == "New"

    async def test_rename_to_own_current_name_is_ok(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        folder = await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Same")

        renamed = await service.rename_folder(folder.id, owner_id=owner_id, name="Same")

        assert renamed.name == "Same"

    async def test_rename_to_another_owned_folder_name_raises_domain_error(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Taken")
        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="Original"
        )

        with pytest.raises(DomainError):
            await service.rename_folder(folder.id, owner_id=owner_id, name="Taken")

    async def test_foreign_owner_gets_not_found(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        stranger_id = uuid.uuid4()
        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="NotYours"
        )

        with pytest.raises(TemplateFolderNotFoundError):
            await service.rename_folder(folder.id, owner_id=stranger_id, name="Hijacked")

    async def test_unknown_folder_id_raises_not_found(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)

        with pytest.raises(TemplateFolderNotFoundError):
            await service.rename_folder(uuid.uuid4(), owner_id=uuid.uuid4(), name="Whatever")


# ---------------------------------------------------------------------------
# delete_folder
# ---------------------------------------------------------------------------


class TestDeleteFolder:
    async def test_owner_can_delete(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        folder = await service.create_folder(tenant_id=tenant_id, owner_id=owner_id, name="Bye")

        await service.delete_folder(folder.id, owner_id=owner_id)

        assert await fake_template_folder_repo.get_by_id(folder.id) is None

    async def test_foreign_owner_gets_not_found(
        self, fake_template_folder_repo: FakeTemplateFolderRepository
    ):
        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        stranger_id = uuid.uuid4()
        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="NotYours"
        )

        with pytest.raises(TemplateFolderNotFoundError):
            await service.delete_folder(folder.id, owner_id=stranger_id)

        # Folder must still exist — the failed delete must not have any effect.
        assert await fake_template_folder_repo.get_by_id(folder.id) is not None

    async def test_delete_unfiles_templates_in_fake(
        self,
        fake_template_folder_repo: FakeTemplateFolderRepository,
        fake_template_repo: FakeTemplateRepository,
    ):
        """The fake emulates the real DB's ON DELETE SET NULL: templates that
        were filed in the deleted folder end up with folder_id=None. The
        real repository relies on the DB FK constraint for this instead."""
        from datetime import datetime, timezone

        from app.domain.entities import Template

        service = make_service(fake_template_folder_repo)
        tenant_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        folder = await service.create_folder(
            tenant_id=tenant_id, owner_id=owner_id, name="ToDelete"
        )

        now = datetime.now(timezone.utc)
        tpl_id = uuid.uuid4()
        fake_template_repo._templates[tpl_id] = Template(
            id=tpl_id,
            tenant_id=tenant_id,
            name="Filed",
            created_by=owner_id,
            folder_id=folder.id,
            created_at=now,
            updated_at=now,
        )

        await service.delete_folder(folder.id, owner_id=owner_id)

        assert fake_template_repo._templates[tpl_id].folder_id is None
