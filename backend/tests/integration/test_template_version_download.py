"""Integration tests — GET /templates/{template_id}/versions/{version_id}/download.

Access matrix (same gate as get_version_structure — any user with template
access): owner OK, shared user OK, unrelated user blocked, admin OK,
version-of-another-template 404.

Follows the style of test_template_endpoint_gates.py: fakes wired in the
integration conftest, per-test get_current_user overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template, TemplateVersion
from app.presentation.middleware.tenant import CurrentUser, get_current_user

# ── Stable IDs ────────────────────────────────────────────────────────────────

CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

OWNER_USER_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")
SHARED_USER_ID = uuid.UUID("88888888-8888-8888-8888-888888888888")
UNRELATED_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEMPLATE_BYTES = b"stored-template-docx-bytes"


def _seed_template_with_version(
    fake_template_repo,
    fake_storage,
    owner_id: uuid.UUID,
    *,
    name: str | None = None,
    version_number: int = 1,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a template + version in the fakes. Returns (template_id, version_id)."""
    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    minio_path = f"{CONFTEST_TENANT_ID}/{template_id}/v{version_number}/template.docx"

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=version_number,
        minio_path=minio_path,
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=name or f"DownloadTemplate-{template_id}",
        description=None,
        current_version=version_number,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = TEMPLATE_BYTES
    return template_id, version_id


def _user_override(user_id: uuid.UUID, role: str) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        tenant_id=CONFTEST_TENANT_ID,
        role=role,
    )


class _OverrideUser:
    """Context manager that swaps get_current_user for a specific user."""

    def __init__(self, app, user: CurrentUser):
        self._app = app
        self._user = user
        self._original = None

    def __enter__(self):
        async def override():
            return self._user

        self._original = self._app.dependency_overrides.get(get_current_user)
        self._app.dependency_overrides[get_current_user] = override
        return self

    def __exit__(self, *exc):
        if self._original is not None:
            self._app.dependency_overrides[get_current_user] = self._original
        else:
            self._app.dependency_overrides.pop(get_current_user, None)
        return False


@pytest.mark.asyncio
async def test_owner_can_download_template_version(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID, name="Contrato Marco"
    )

    with _OverrideUser(app, _user_override(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    assert response.content == TEMPLATE_BYTES
    assert response.headers["content-type"].startswith(DOCX_MIME)
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "_v1.docx" in disposition


@pytest.mark.asyncio
async def test_shared_user_can_download_template_version(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=SHARED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=OWNER_USER_ID,
    )

    with _OverrideUser(app, _user_override(SHARED_USER_ID, "document_generator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 200, response.text
    assert response.content == TEMPLATE_BYTES


@pytest.mark.asyncio
async def test_unrelated_user_blocked_from_template_version_download(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, ver_id = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )

    with _OverrideUser(app, _user_override(UNRELATED_USER_ID, "user")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{ver_id}/download",
            headers=auth_headers,
        )

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_admin_can_download_template_version(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    # Conftest default user is admin — no override needed.
    tpl_id, ver_id = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )

    response = await async_client.get(
        f"/api/v1/templates/{tpl_id}/versions/{ver_id}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.content == TEMPLATE_BYTES


@pytest.mark.asyncio
async def test_version_of_another_template_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_a, _ = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )
    _, ver_b = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )

    with _OverrideUser(app, _user_override(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_a}/versions/{ver_b}/download",
            headers=auth_headers,
        )

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_unknown_version_returns_404(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    tpl_id, _ = _seed_template_with_version(
        fake_template_repo, fake_storage, OWNER_USER_ID
    )

    with _OverrideUser(app, _user_override(OWNER_USER_ID, "template_creator")):
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/versions/{uuid.uuid4()}/download",
            headers=auth_headers,
        )

    assert response.status_code == 404, response.text
