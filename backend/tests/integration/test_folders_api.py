"""Integration tests — /api/v1/folders/* endpoints.

Folders are PERSONAL (owner-scoped) and FLAT — they organize only the
caller's own templates. All tests use the fakes wired up in the
integration conftest (FakeTemplateFolderRepository linked to
fake_template_repo so delete() can emulate ON DELETE SET NULL).
"""

from __future__ import annotations

import uuid

import pytest

from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeTemplateFolderRepository, FakeTemplateRepository

CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# A second user in the same tenant, distinct from the conftest admin user.
USER_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _override_as_user_b(app):
    """Context-manager-less helper: set get_current_user override to user B,
    returning the original override so the caller can restore it in finally."""
    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    return original


def _restore(app, original):
    if original is not None:
        app.dependency_overrides[get_current_user] = original
    else:
        app.dependency_overrides.pop(get_current_user, None)


# ── Unauthenticated access ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_folders_without_auth_returns_401(async_client, app):
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/folders")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Create ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_folder_returns_201(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "Contratos2026"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Contratos2026"
    assert data["template_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_create_folder_strips_name(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "  Espacios  "}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Espacios"


@pytest.mark.asyncio
async def test_create_folder_empty_name_returns_422(async_client, auth_headers):
    response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "   "}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_folder_duplicate_name_returns_409(async_client, auth_headers):
    await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "DuplicadaFolder"}
    )
    response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "DuplicadaFolder"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_folder_same_name_allowed_for_different_owner(
    async_client, app, auth_headers
):
    await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "SharedNameFolder"}
    )

    original = _override_as_user_b(app)
    try:
        response = await async_client.post(
            "/api/v1/folders", headers=auth_headers, json={"name": "SharedNameFolder"}
        )
        assert response.status_code == 201
    finally:
        _restore(app, original)


# ── List ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_folders_returns_only_own_folders(async_client, app, auth_headers):
    await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "OwnedByAdminList"}
    )

    original = _override_as_user_b(app)
    try:
        await async_client.post(
            "/api/v1/folders", headers=auth_headers, json={"name": "OwnedByUserBList"}
        )
        response = await async_client.get("/api/v1/folders", headers=auth_headers)
        assert response.status_code == 200
        names = [f["name"] for f in response.json()["folders"]]
        assert "OwnedByUserBList" in names
        assert "OwnedByAdminList" not in names
    finally:
        _restore(app, original)


@pytest.mark.asyncio
async def test_list_folders_includes_template_count(
    async_client, auth_headers, fake_template_repo: FakeTemplateRepository
):
    from datetime import datetime, timezone

    from app.domain.entities import Template

    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "CountedFolder"}
    )
    folder_id = uuid.UUID(create_response.json()["id"])

    now = datetime.now(timezone.utc)
    for i in range(3):
        tpl_id = uuid.uuid4()
        fake_template_repo._templates[tpl_id] = Template(
            id=tpl_id,
            tenant_id=CONFTEST_TENANT_ID,
            name=f"CountedTpl{i}-{tpl_id}",
            created_by=CONFTEST_USER_ID,
            folder_id=folder_id,
            created_at=now,
            updated_at=now,
        )

    response = await async_client.get("/api/v1/folders", headers=auth_headers)
    assert response.status_code == 200
    match = next(f for f in response.json()["folders"] if f["id"] == str(folder_id))
    assert match["template_count"] == 3


# ── Update (rename) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_folder_returns_200(async_client, auth_headers):
    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "BeforeRename"}
    )
    folder_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/folders/{folder_id}", headers=auth_headers, json={"name": "AfterRename"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "AfterRename"


@pytest.mark.asyncio
async def test_rename_folder_to_own_current_name_is_ok(async_client, auth_headers):
    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "SameNameFolder"}
    )
    folder_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/folders/{folder_id}",
        headers=auth_headers,
        json={"name": "SameNameFolder"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rename_folder_to_taken_name_returns_409(async_client, auth_headers):
    await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "TakenFolderName"}
    )
    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "OriginalFolderName"}
    )
    folder_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/folders/{folder_id}",
        headers=auth_headers,
        json={"name": "TakenFolderName"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rename_foreign_folder_returns_404(async_client, app, auth_headers):
    """A folder owned by another user cannot be renamed — 404, not 403 (non-leaking)."""
    original = _override_as_user_b(app)
    try:
        create_response = await async_client.post(
            "/api/v1/folders", headers=auth_headers, json={"name": "UserBOwnedRename"}
        )
        folder_id = create_response.json()["id"]
    finally:
        _restore(app, original)

    # Back to the conftest admin user — tries to rename user B's folder.
    response = await async_client.patch(
        f"/api/v1/folders/{folder_id}",
        headers=auth_headers,
        json={"name": "Hijacked"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rename_unknown_folder_returns_404(async_client, auth_headers):
    response = await async_client.patch(
        f"/api/v1/folders/{uuid.uuid4()}",
        headers=auth_headers,
        json={"name": "DoesNotExist"},
    )
    assert response.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_folder_returns_204(async_client, auth_headers):
    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "ToBeDeleted"}
    )
    folder_id = create_response.json()["id"]

    response = await async_client.delete(f"/api/v1/folders/{folder_id}", headers=auth_headers)
    assert response.status_code == 204

    list_response = await async_client.get("/api/v1/folders", headers=auth_headers)
    names = [f["name"] for f in list_response.json()["folders"]]
    assert "ToBeDeleted" not in names


@pytest.mark.asyncio
async def test_delete_foreign_folder_returns_404(async_client, app, auth_headers):
    original = _override_as_user_b(app)
    try:
        create_response = await async_client.post(
            "/api/v1/folders", headers=auth_headers, json={"name": "UserBOwnedDelete"}
        )
        folder_id = create_response.json()["id"]
    finally:
        _restore(app, original)

    response = await async_client.delete(f"/api/v1/folders/{folder_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_folder_returns_404(async_client, auth_headers):
    response = await async_client.delete(
        f"/api/v1/folders/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_folder_unfiles_templates(
    async_client,
    auth_headers,
    fake_template_repo: FakeTemplateRepository,
    fake_template_folder_repo: FakeTemplateFolderRepository,
):
    """Deleting a folder unfiles its templates (folder_id -> None) rather
    than deleting them. The fake emulates the real DB's ON DELETE SET NULL."""
    from datetime import datetime, timezone

    from app.domain.entities import Template

    create_response = await async_client.post(
        "/api/v1/folders", headers=auth_headers, json={"name": "WillBeDeletedWithTpl"}
    )
    folder_id = uuid.UUID(create_response.json()["id"])

    now = datetime.now(timezone.utc)
    tpl_id = uuid.uuid4()
    fake_template_repo._templates[tpl_id] = Template(
        id=tpl_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=f"FiledTplToUnfile-{tpl_id}",
        created_by=CONFTEST_USER_ID,
        folder_id=folder_id,
        created_at=now,
        updated_at=now,
    )

    response = await async_client.delete(
        f"/api/v1/folders/{folder_id}", headers=auth_headers
    )
    assert response.status_code == 204

    # Template must still exist (never deleted) but must be unfiled.
    assert tpl_id in fake_template_repo._templates
    assert fake_template_repo._templates[tpl_id].folder_id is None
