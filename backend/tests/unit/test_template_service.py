"""Unit tests for TemplateService (task 3.4)."""
import uuid
from uuid import UUID

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.template_service import TemplateService
from app.domain.entities import AuditAction
from app.domain.exceptions import (
    InvalidTemplateError,
    TemplateAccessDeniedError,
    TemplateNotFoundError,
)
from tests.fakes import (
    FakeAuditRepository,
    FakeStorageService,
    FakeTemplateEngine,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_service(
    fake_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    fake_engine: FakeTemplateEngine,
    audit_service: AuditService | None = None,
) -> TemplateService:
    return TemplateService(
        repository=fake_repo,
        storage=fake_storage,
        engine=fake_engine,
        audit_service=audit_service,
    )


async def upload_template_helper(
    service: TemplateService,
    name: str = "Test Template",
    variables: list[str] | None = None,
) -> tuple[dict, str, str]:
    """Upload a template and return (result, tenant_id_str, user_id_str)."""
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    if variables is None:
        variables = ["name", "company"]

    # Reconfigure engine to return our variables
    service._engine.variables_to_return = variables

    result = await service.upload_template(
        name=name,
        file_bytes=b"fake-docx-bytes",
        file_size=len(b"fake-docx-bytes"),
        tenant_id=tenant_id,
        created_by=user_id,
        description=None,
    )
    return result, tenant_id, user_id


# ---------------------------------------------------------------------------
# upload_template
# ---------------------------------------------------------------------------


class TestUploadTemplate:
    async def test_creates_record_in_repo(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service)

        assert len(fake_template_repo._templates) == 1

    async def test_stores_bytes_in_storage(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service)

        template_files = [
            (b, p) for (b, p) in fake_storage.files if b == "templates"
        ]
        assert len(template_files) == 1
        assert fake_storage.files[template_files[0]] == b"fake-docx-bytes"

    async def test_returns_template_with_correct_name(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service, name="My Special Template")

        template = list(fake_template_repo._templates.values())[0]
        assert template.name == "My Special Template"

    async def test_version_one_is_created(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service)

        template = list(fake_template_repo._templates.values())[0]
        assert template.current_version == 1
        assert len(template.versions) == 1

    async def test_invalid_template_raises_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When engine.extract_variables raises, service raises InvalidTemplateError."""
        fake_template_engine.should_fail = True

        # Patch extract_variables to raise
        async def _raise(file_bytes):
            raise ValueError("bad docx")

        fake_template_engine.extract_variables = _raise

        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        with pytest.raises(InvalidTemplateError):
            await service.upload_template(
                name="Bad",
                file_bytes=b"not-a-docx",
                file_size=10,
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )


# ---------------------------------------------------------------------------
# upload_new_version
# ---------------------------------------------------------------------------


class TestUploadNewVersion:
    async def test_increments_version(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, tenant_id, _ = await upload_template_helper(service, variables=["name"])

        template = list(fake_template_repo._templates.values())[0]
        template_id = str(template.id)

        new_variables = ["name", "email"]
        fake_template_engine.variables_to_return = new_variables

        v2_result = await service.upload_new_version(
            template_id=template_id,
            file_bytes=b"updated-docx-bytes",
            file_size=len(b"updated-docx-bytes"),
            tenant_id=tenant_id,
        )

        assert v2_result["new_version"] == 2

    async def test_new_version_stored_in_storage(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, tenant_id, _ = await upload_template_helper(service, variables=["x"])

        template = list(fake_template_repo._templates.values())[0]
        template_id = str(template.id)
        fake_template_engine.variables_to_return = ["x", "y"]

        await service.upload_new_version(
            template_id=template_id,
            file_bytes=b"v2-bytes",
            file_size=8,
            tenant_id=tenant_id,
        )

        template_files = [
            (b, p) for (b, p) in fake_storage.files if b == "templates"
        ]
        # Should have v1 and v2
        assert len(template_files) == 2

    async def test_unknown_template_raises_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        with pytest.raises(TemplateNotFoundError):
            await service.upload_new_version(
                template_id=str(uuid.uuid4()),
                file_bytes=b"bytes",
                file_size=5,
                tenant_id=str(uuid.uuid4()),
            )

    async def test_version_increments_correctly_after_multiple_uploads(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, tenant_id, _ = await upload_template_helper(service, variables=["a"])

        template = list(fake_template_repo._templates.values())[0]
        template_id = str(template.id)

        fake_template_engine.variables_to_return = ["a"]
        v2 = await service.upload_new_version(
            template_id=template_id, file_bytes=b"v2", file_size=2, tenant_id=tenant_id
        )
        v3 = await service.upload_new_version(
            template_id=template_id, file_bytes=b"v3", file_size=2, tenant_id=tenant_id
        )

        assert v2["new_version"] == 2
        assert v3["new_version"] == 3


# ---------------------------------------------------------------------------
# delete_template
# ---------------------------------------------------------------------------


class TestDeleteTemplate:
    async def test_removes_from_repo(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service)

        template = list(fake_template_repo._templates.values())[0]
        await service.delete_template(template.id)

        assert len(fake_template_repo._templates) == 0

    async def test_delete_nonexistent_raises_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        with pytest.raises(TemplateNotFoundError):
            await service.delete_template(uuid.uuid4())


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------


class TestListTemplates:
    async def test_returns_paginated_results(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        # Upload 3 templates
        for i in range(3):
            fake_template_engine.variables_to_return = [f"var{i}"]
            await service.upload_template(
                name=f"Template {i}",
                file_bytes=b"bytes",
                file_size=5,
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )

        items, total = await service.list_templates(page=1, size=20)
        assert total == 3
        assert len(items) == 3

    async def test_pagination_works(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        for i in range(5):
            fake_template_engine.variables_to_return = ["x"]
            await service.upload_template(
                name=f"T{i}",
                file_bytes=b"b",
                file_size=1,
                tenant_id=str(uuid.uuid4()),
                created_by=str(uuid.uuid4()),
            )

        page1, total = await service.list_templates(page=1, size=3)
        page2, _ = await service.list_templates(page=2, size=3)

        assert total == 5
        assert len(page1) == 3
        assert len(page2) == 2

    async def test_empty_list(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        items, total = await service.list_templates()
        assert items == []
        assert total == 0


# ---------------------------------------------------------------------------
# Helper: seed a template owned by a specific user
# ---------------------------------------------------------------------------


async def seed_owned_template(
    service: TemplateService,
    fake_repo: FakeTemplateRepository,
    fake_engine: FakeTemplateEngine,
    tenant_id: str,
    owner_id: str,
    name: str = "Template",
):
    """Upload a template owned by owner_id in tenant_id. Returns the template object."""
    fake_engine.variables_to_return = ["var"]
    return await service.upload_template(
        name=name,
        file_bytes=b"fake-docx",
        file_size=9,
        tenant_id=tenant_id,
        created_by=owner_id,
    )


# ---------------------------------------------------------------------------
# Task 5.1: _check_access
# ---------------------------------------------------------------------------


class TestCheckAccess:
    """_check_access enforces ownership/share rules correctly."""

    async def test_owner_allowed_for_read(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Owner can read their own template (require_owner=False)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        # Should not raise
        await service._check_access(
            template_id=tpl.id,
            user_id=uuid.UUID(owner_id),
            role="user",
            require_owner=False,
        )

    async def test_owner_allowed_for_write(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Owner can perform owner-only operations (require_owner=True)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        # Should not raise
        await service._check_access(
            template_id=tpl.id,
            user_id=uuid.UUID(owner_id),
            role="user",
            require_owner=True,
        )

    async def test_shared_user_allowed_for_read(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Shared user can read (require_owner=False)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        shared_user_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        await fake_template_repo.add_share(
            template_id=tpl.id,
            user_id=shared_user_id,
            tenant_id=tpl.tenant_id,
            shared_by=tpl.created_by,
        )
        # Should not raise
        await service._check_access(
            template_id=tpl.id,
            user_id=shared_user_id,
            role="user",
            require_owner=False,
        )

    async def test_shared_user_denied_for_version(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Shared user cannot upload new versions (require_owner=True)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        shared_user_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        await fake_template_repo.add_share(
            template_id=tpl.id,
            user_id=shared_user_id,
            tenant_id=tpl.tenant_id,
            shared_by=tpl.created_by,
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service._check_access(
                template_id=tpl.id,
                user_id=shared_user_id,
                role="user",
                require_owner=True,
            )

    async def test_shared_user_denied_for_delete(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Shared user cannot delete (require_owner=True)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        shared_user_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        await fake_template_repo.add_share(
            template_id=tpl.id,
            user_id=shared_user_id,
            tenant_id=tpl.tenant_id,
            shared_by=tpl.created_by,
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service.delete_template(
                template_id=tpl.id,
                user_id=shared_user_id,
                role="user",
            )

    async def test_unrelated_user_denied_for_read(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Unrelated user gets TemplateAccessDeniedError for read access."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        unrelated_user_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service._check_access(
                template_id=tpl.id,
                user_id=unrelated_user_id,
                role="user",
                require_owner=False,
            )

    async def test_unrelated_user_denied_for_write(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Unrelated user gets TemplateAccessDeniedError for owner-only access."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        unrelated_user_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service._check_access(
                template_id=tpl.id,
                user_id=unrelated_user_id,
                role="user",
                require_owner=True,
            )

    async def test_admin_bypasses_read_check(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Admin can access any template regardless of ownership (require_owner=False)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        # Should not raise
        await service._check_access(
            template_id=tpl.id,
            user_id=admin_id,
            role="admin",
            require_owner=False,
        )

    async def test_admin_bypasses_write_check(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Admin can perform owner-only operations on any template (require_owner=True)."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = uuid.uuid4()

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        # Should not raise
        await service._check_access(
            template_id=tpl.id,
            user_id=admin_id,
            role="admin",
            require_owner=True,
        )


# ---------------------------------------------------------------------------
# Task 5.2: share_template / unshare_template
# ---------------------------------------------------------------------------


class TestShareTemplate:
    """share_template and unshare_template enforce ownership rules."""

    async def test_non_owner_cannot_share(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Non-owner attempting to share gets TemplateAccessDeniedError."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        non_owner_id = uuid.uuid4()
        target_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service.share_template(
                template_id=tpl.id,
                user_id=target_user_id,
                current_user_id=non_owner_id,
                role="user",
                tenant_id=tenant_uuid,
            )

    async def test_owner_can_share_successfully(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Owner can share their template with another user."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        target_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        share = await service.share_template(
            template_id=tpl.id,
            user_id=target_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )

        assert share.template_id == tpl.id
        assert share.user_id == target_user_id

    async def test_duplicate_share_is_idempotent(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Sharing the same user twice does not raise an error."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        target_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        await service.share_template(
            template_id=tpl.id,
            user_id=target_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )
        # Second call must not raise
        share2 = await service.share_template(
            template_id=tpl.id,
            user_id=target_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )
        # Only one share record should exist
        shares = await fake_template_repo.list_shares(tpl.id)
        assert len(shares) == 1
        assert share2.user_id == target_user_id

    async def test_non_owner_cannot_unshare(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Non-owner attempting to unshare gets TemplateAccessDeniedError."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        shared_user_id = uuid.uuid4()
        non_owner_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        await service.share_template(
            template_id=tpl.id,
            user_id=shared_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )

        with pytest.raises(TemplateAccessDeniedError):
            await service.unshare_template(
                template_id=tpl.id,
                user_id=shared_user_id,
                current_user_id=non_owner_id,
                role="user",
            )

    async def test_owner_can_unshare_successfully(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Owner can revoke a previously granted share; user loses access."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        shared_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        await service.share_template(
            template_id=tpl.id,
            user_id=shared_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )

        # Confirm user has access before unshare
        has_before = await fake_template_repo.has_access(
            tpl.id, shared_user_id, "user"
        )
        assert has_before is True

        await service.unshare_template(
            template_id=tpl.id,
            user_id=shared_user_id,
            current_user_id=tpl.created_by,
            role="user",
        )

        has_after = await fake_template_repo.has_access(
            tpl.id, shared_user_id, "user"
        )
        assert has_after is False

    async def test_admin_can_share_any_template(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Admin can share a template they don't own."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = uuid.uuid4()
        target_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )

        share = await service.share_template(
            template_id=tpl.id,
            user_id=target_user_id,
            current_user_id=admin_id,
            role="admin",
            tenant_id=tenant_uuid,
        )

        assert share.template_id == tpl.id
        assert share.user_id == target_user_id

    async def test_admin_can_unshare_any_template(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Admin can unshare a template they don't own."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())
        admin_id = uuid.uuid4()
        shared_user_id = uuid.uuid4()
        tenant_uuid = uuid.UUID(tenant_id)

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_id, owner_id
        )
        # Owner shares first
        await service.share_template(
            template_id=tpl.id,
            user_id=shared_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tenant_uuid,
        )

        # Admin unshares — should not raise
        await service.unshare_template(
            template_id=tpl.id,
            user_id=shared_user_id,
            current_user_id=admin_id,
            role="admin",
        )

        has_access = await fake_template_repo.has_access(
            tpl.id, shared_user_id, "user"
        )
        assert has_access is False

    async def test_cross_tenant_share_raises_error(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Sharing with a user from a different tenant raises TemplateSharingError."""
        from app.domain.exceptions import TemplateSharingError

        service = make_service(fake_template_repo, fake_storage, fake_template_engine)

        # Template belongs to tenant A
        tenant_a_id = str(uuid.uuid4())
        owner_id = str(uuid.uuid4())

        tpl = await seed_owned_template(
            service, fake_template_repo, fake_template_engine, tenant_a_id, owner_id
        )

        # Target user is from tenant B (different tenant)
        tenant_b_uuid = uuid.uuid4()  # different from tenant_a_id
        target_user_id = uuid.uuid4()

        with pytest.raises(TemplateSharingError):
            await service.share_template(
                template_id=tpl.id,
                user_id=target_user_id,
                current_user_id=tpl.created_by,
                role="user",
                tenant_id=tenant_b_uuid,  # tenant B — does not match template's tenant
            )


# ---------------------------------------------------------------------------
# Task 5.3: list_templates (owned + shared + admin)
# ---------------------------------------------------------------------------


class TestListTemplatesAccessFilter:
    """list_templates returns only templates the user can access."""

    async def test_user_sees_only_own_and_shared(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """User sees their own templates plus templates shared with them."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        tenant_uuid = uuid.UUID(tenant_id)
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        # user_a owns T1
        fake_template_engine.variables_to_return = ["x"]
        tpl_a = await service.upload_template(
            name="T1",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(user_a_id),
        )

        # user_b owns T2 — user_a has NOT been shared
        tpl_b = await service.upload_template(
            name="T2",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(user_b_id),
        )

        # user_b owns T3 — shared with user_a
        tpl_c = await service.upload_template(
            name="T3",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(user_b_id),
        )
        await fake_template_repo.add_share(
            template_id=tpl_c.id,
            user_id=user_a_id,
            tenant_id=tenant_uuid,
            shared_by=user_b_id,
        )

        items, total = await service.list_templates(
            user_id=user_a_id, role="user"
        )

        ids = {t.id for t in items}
        assert tpl_a.id in ids        # user_a owns T1
        assert tpl_c.id in ids        # shared with user_a
        assert tpl_b.id not in ids    # not shared, not owned
        assert total == 2

    async def test_access_type_is_correct(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Templates owned by user show access_type='owned'; shared show 'shared'."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        tenant_uuid = uuid.UUID(tenant_id)
        user_a_id = uuid.uuid4()
        user_b_id = uuid.uuid4()

        fake_template_engine.variables_to_return = ["x"]
        tpl_owned = await service.upload_template(
            name="Owned",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(user_a_id),
        )

        tpl_from_b = await service.upload_template(
            name="SharedByB",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(user_b_id),
        )
        await fake_template_repo.add_share(
            template_id=tpl_from_b.id,
            user_id=user_a_id,
            tenant_id=tenant_uuid,
            shared_by=user_b_id,
        )

        items, _ = await service.list_templates(user_id=user_a_id, role="user")

        by_id = {t.id: t for t in items}
        assert by_id[tpl_owned.id].access_type == "owned"
        assert by_id[tpl_from_b.id].access_type == "shared"

    async def test_admin_sees_all_templates(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """Admin sees all templates in the tenant, regardless of ownership."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        admin_id = uuid.uuid4()

        fake_template_engine.variables_to_return = ["x"]
        for i in range(3):
            await service.upload_template(
                name=f"AdminVisible{i}",
                file_bytes=b"bytes",
                file_size=5,
                tenant_id=tenant_id,
                created_by=str(uuid.uuid4()),  # each template has a different owner
            )

        items, total = await service.list_templates(user_id=admin_id, role="admin")

        assert total >= 3  # may include templates from other tests in the same repo
        # All 3 admin-visible templates must appear
        names = {t.name for t in items}
        for i in range(3):
            assert f"AdminVisible{i}" in names

    async def test_user_with_no_templates_sees_empty_list(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """User with no owned or shared templates sees an empty list."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tenant_id = str(uuid.uuid4())
        lonely_user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()

        fake_template_engine.variables_to_return = ["x"]
        # Other user uploads a template — not shared with lonely_user
        await service.upload_template(
            name="Private",
            file_bytes=b"bytes",
            file_size=5,
            tenant_id=tenant_id,
            created_by=str(other_user_id),
        )

        items, total = await service.list_templates(
            user_id=lonely_user_id, role="user"
        )

        assert total == 0
        assert items == []


# ---------------------------------------------------------------------------
# Phase 5.5 — Audit integration (task 5.5 RED + 5.6 GREEN)
# ---------------------------------------------------------------------------


import asyncio as _asyncio


def make_sync_audit_service(repo: FakeAuditRepository) -> AuditService:
    """Return an AuditService backed by FakeAuditRepository.

    Uses the real log() which calls asyncio.create_task(_write(entry)).
    Tests must await asyncio.sleep(0) after calling service methods to allow
    the scheduled task to complete before asserting on the repo state.
    """
    return AuditService(audit_repo=repo)


class TestTemplateAuditIntegration:
    """TemplateService emits audit events for all mutating operations."""

    async def test_upload_template_logs_audit(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """upload_template() logs TEMPLATE_UPLOAD."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, audit_svc)

        await upload_template_helper(service)
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.TEMPLATE_UPLOAD

    async def test_upload_new_version_logs_audit(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """upload_new_version() logs TEMPLATE_VERSION."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, audit_svc)

        result, tenant_id, user_id = await upload_template_helper(service)
        template_id = str(result.id)
        await _asyncio.sleep(0)  # Drain upload_template audit task
        fake_audit_repo._entries.clear()

        await service.upload_new_version(
            template_id=template_id,
            file_bytes=b"new-version-bytes",
            file_size=len(b"new-version-bytes"),
            tenant_id=tenant_id,
            user_id=user_id,
            role="user",
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.TEMPLATE_VERSION

    async def test_delete_template_logs_audit(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """delete_template() logs TEMPLATE_DELETE."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, audit_svc)

        result, tenant_id, user_id = await upload_template_helper(service)
        template_id = result.id
        await _asyncio.sleep(0)  # Drain upload_template audit task
        fake_audit_repo._entries.clear()

        await service.delete_template(
            template_id=template_id,
            user_id=UUID(user_id),
            role="user",
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.TEMPLATE_DELETE

    async def test_share_template_logs_audit(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """share_template() logs TEMPLATE_SHARE."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, audit_svc)

        result, tenant_id, user_id = await upload_template_helper(service)
        template_id = result.id
        await _asyncio.sleep(0)  # Drain upload_template audit task
        fake_audit_repo._entries.clear()

        target_user_id = uuid.uuid4()
        await service.share_template(
            template_id=template_id,
            user_id=target_user_id,
            current_user_id=UUID(user_id),
            role="user",
            tenant_id=UUID(tenant_id),
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.TEMPLATE_SHARE

    async def test_unshare_template_logs_audit(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
        fake_audit_repo: FakeAuditRepository,
    ):
        """unshare_template() logs TEMPLATE_UNSHARE."""
        audit_svc = make_sync_audit_service(fake_audit_repo)
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, audit_svc)

        result, tenant_id, user_id = await upload_template_helper(service)
        template_id = result.id
        await _asyncio.sleep(0)  # Drain upload_template audit task
        target_user_id = uuid.uuid4()

        # Share first, then unshare
        await service.share_template(
            template_id=template_id,
            user_id=target_user_id,
            current_user_id=UUID(user_id),
            role="user",
            tenant_id=UUID(tenant_id),
        )
        await _asyncio.sleep(0)  # Drain share audit task
        fake_audit_repo._entries.clear()

        await service.unshare_template(
            template_id=template_id,
            user_id=target_user_id,
            current_user_id=UUID(user_id),
            role="user",
        )
        # Yield to event loop so fire-and-forget create_task completes
        await _asyncio.sleep(0)

        assert len(fake_audit_repo._entries) == 1
        assert fake_audit_repo._entries[0].action == AuditAction.TEMPLATE_UNSHARE

    async def test_no_audit_service_does_not_raise(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """With audit_service=None, all template operations complete without error."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine, None)

        result, _, _ = await upload_template_helper(service)
        assert result is not None  # No exception raised


# ---------------------------------------------------------------------------
# Task 7.3 — Quota integration with TemplateService
# ---------------------------------------------------------------------------


from app.domain.entities.subscription_tier import FREE_TIER_ID  # noqa: E402
from app.domain.exceptions import QuotaExceededError  # noqa: E402
from tests.fakes import FakeQuotaService  # noqa: E402


def make_service_with_quota(
    fake_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    fake_engine: FakeTemplateEngine,
    fake_quota_svc: FakeQuotaService,
) -> TemplateService:
    """TemplateService wired with a FakeQuotaService and FREE_TIER_ID."""
    return TemplateService(
        repository=fake_repo,
        storage=fake_storage,
        engine=fake_engine,
        quota_service=fake_quota_svc,
        tier_id=FREE_TIER_ID,
    )


class TestUploadTemplateWithQuota:
    """upload_template() propagates QuotaExceededError from quota_service."""

    async def test_quota_exceeded_propagates_on_upload(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When template quota is exceeded, upload raises QuotaExceededError."""
        quota_svc = FakeQuotaService(exceeded_resource="max_templates")
        service = make_service_with_quota(
            fake_template_repo, fake_storage, fake_template_engine, quota_svc
        )

        with pytest.raises(QuotaExceededError) as exc_info:
            await upload_template_helper(service)

        assert exc_info.value.limit_type == "max_templates"

    async def test_no_template_created_when_quota_exceeded(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When quota raises, no template record is created."""
        quota_svc = FakeQuotaService(exceeded_resource="max_templates")
        service = make_service_with_quota(
            fake_template_repo, fake_storage, fake_template_engine, quota_svc
        )

        try:
            await upload_template_helper(service)
        except Exception:
            pass

        assert len(fake_template_repo._templates) == 0

    async def test_quota_service_none_is_backward_compat_for_upload(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """quota_service=None → no quota check, upload succeeds as before."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        result, _, _ = await upload_template_helper(service)

        assert result is not None
        assert len(fake_template_repo._templates) == 1


class TestShareTemplateWithQuota:
    """share_template() propagates QuotaExceededError from quota_service."""

    async def test_quota_exceeded_propagates_on_share(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When share quota is exceeded, share_template raises QuotaExceededError."""
        # First upload the template with no quota check
        base_service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tpl, tenant_id, owner_id = await upload_template_helper(base_service)

        # Now wire quota that blocks shares
        quota_svc = FakeQuotaService(exceeded_resource="max_template_shares")
        service = make_service_with_quota(
            fake_template_repo, fake_storage, fake_template_engine, quota_svc
        )

        with pytest.raises(QuotaExceededError) as exc_info:
            await service.share_template(
                template_id=tpl.id,
                user_id=uuid.uuid4(),
                current_user_id=tpl.created_by,
                role="user",
                tenant_id=tpl.tenant_id,
            )

        assert exc_info.value.limit_type == "max_template_shares"

    async def test_no_share_created_when_quota_exceeded(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """When share quota raises, no share record is created."""
        base_service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tpl, tenant_id, owner_id = await upload_template_helper(base_service)

        quota_svc = FakeQuotaService(exceeded_resource="max_template_shares")
        service = make_service_with_quota(
            fake_template_repo, fake_storage, fake_template_engine, quota_svc
        )

        try:
            await service.share_template(
                template_id=tpl.id,
                user_id=uuid.uuid4(),
                current_user_id=tpl.created_by,
                role="user",
                tenant_id=tpl.tenant_id,
            )
        except Exception:
            pass

        shares = await fake_template_repo.list_shares(tpl.id)
        assert len(shares) == 0

    async def test_quota_service_none_is_backward_compat_for_share(
        self,
        fake_template_repo: FakeTemplateRepository,
        fake_storage: FakeStorageService,
        fake_template_engine: FakeTemplateEngine,
    ):
        """quota_service=None → share succeeds without quota check."""
        service = make_service(fake_template_repo, fake_storage, fake_template_engine)
        tpl, tenant_id, owner_id = await upload_template_helper(service)

        target_user_id = uuid.uuid4()
        share = await service.share_template(
            template_id=tpl.id,
            user_id=target_user_id,
            current_user_id=tpl.created_by,
            role="user",
            tenant_id=tpl.tenant_id,
        )

        assert share.template_id == tpl.id
        assert share.user_id == target_user_id
