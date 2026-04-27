"""Integration tests — /api/v1/templates/* endpoints.

All tests use the fakes wired up in the integration conftest.  The template
service override provides FakeTemplateRepository + FakeStorageService +
FakeTemplateEngine.

Template upload also calls get_template_engine() directly (outside DI) for
validation.  We monkeypatch that call to return our FakeTemplateEngine so
validation always passes.
"""

from __future__ import annotations

import io
import uuid

import pytest

from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeTemplateRepository

# Stable IDs from integration conftest
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# A second user in the same tenant (different from the admin test_user)
USER_B_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


# ── Unauthenticated access ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_templates_without_auth_returns_401(async_client, app):
    from app.presentation.middleware.tenant import get_current_user

    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/templates")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


@pytest.mark.asyncio
async def test_upload_template_without_auth_returns_401(async_client, app):
    from app.presentation.middleware.tenant import get_current_user

    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.post(
            "/api/v1/templates/upload",
            data={"name": "Test"},
            files={"file": ("test.docx", b"fake-bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Authenticated list ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_templates_returns_200(async_client, auth_headers):
    response = await async_client.get("/api/v1/templates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_list_templates_pagination_fields_present(async_client, auth_headers):
    response = await async_client.get(
        "/api/v1/templates", headers=auth_headers, params={"page": 1, "size": 10}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["size"] == 10


# ── Template upload ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_template_creates_template(
    async_client, auth_headers, monkeypatch, fake_template_engine
):
    """Uploading a template returns 201 and the template appears in the list."""
    # Configure the shared fake engine (used by both the service and the direct call)
    fake_template_engine.variables_to_return = ["name", "date"]

    # Patch get_template_engine() used directly inside the upload endpoint for validation
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )

    docx_bytes = b"fake-docx-content"
    response = await async_client.post(
        "/api/v1/templates/upload",
        headers=auth_headers,
        data={"name": "My Integration Template"},
        files={
            "file": (
                "template.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Integration Template"
    assert "id" in data
    assert data["version"] == 1
    assert set(data["variables"]) == {"name", "date"}

    # Reset for subsequent tests
    fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_upload_template_appears_in_list(
    async_client, auth_headers, monkeypatch, fake_template_engine
):
    """After upload, the template is returned in GET /templates."""
    fake_template_engine.variables_to_return = ["title"]
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )

    docx_bytes = b"fake-docx-for-list-test"
    upload_response = await async_client.post(
        "/api/v1/templates/upload",
        headers=auth_headers,
        data={"name": "ListableTemplate"},
        files={
            "file": (
                "template.docx",
                io.BytesIO(docx_bytes),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload_response.status_code == 201
    created_id = upload_response.json()["id"]

    # Use the unique name as a search filter so the assertion is not affected by
    # the number of templates accumulated in the session-scoped fake repository.
    # Without this, a full test suite run can push the new template past page 1
    # (default size=20), causing a false negative while the test passes in isolation.
    list_response = await async_client.get(
        "/api/v1/templates",
        headers=auth_headers,
        params={"search": "ListableTemplate"},
    )
    assert list_response.status_code == 200
    ids = [item["id"] for item in list_response.json()["items"]]
    assert created_id in ids

    # Reset
    fake_template_engine.variables_to_return = []


@pytest.mark.asyncio
async def test_upload_empty_file_returns_400(async_client, auth_headers, monkeypatch, fake_template_engine):
    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )

    response = await async_client.post(
        "/api/v1/templates/upload",
        headers=auth_headers,
        data={"name": "EmptyTemplate"},
        files={
            "file": (
                "empty.docx",
                io.BytesIO(b""),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 400


# ── Task 5.5: Template visibility / sharing integration tests ─────────────────


def _upload_template_as_user(
    template_name: str,
    owner_id: uuid.UUID,
    fake_template_repo: FakeTemplateRepository,
) -> uuid.UUID:
    """Directly seed a template in the fake repo for a specific owner.

    Returns the template_id.
    """
    from datetime import datetime, timezone
    from app.domain.entities import Template, TemplateVersion

    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx",
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=template_name,
        description=None,
        current_version=1,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    return template_id


@pytest.mark.asyncio
async def test_private_by_default_user_b_cannot_list(
    async_client, app, auth_headers, fake_template_repo
):
    """User B cannot see user A's template in the list (private by default)."""
    # Seed a template owned by the conftest admin user (user A)
    tpl_id = _upload_template_as_user(
        "PrivateByDefault", CONFTEST_USER_ID, fake_template_repo
    )

    # Override current_user to user B (a regular user)
    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.get("/api/v1/templates", headers=auth_headers)
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert str(tpl_id) not in ids
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_private_by_default_user_b_gets_403_on_get(
    async_client, app, auth_headers, fake_template_repo
):
    """User B gets 403 when trying to GET user A's private template."""
    tpl_id = _upload_template_as_user(
        "PrivateGet403", CONFTEST_USER_ID, fake_template_repo
    )

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}", headers=auth_headers
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_after_sharing_user_b_sees_in_list(
    async_client, app, auth_headers, fake_template_repo
):
    """After sharing, user B sees the template in the list."""
    tpl_id = _upload_template_as_user(
        "SharedVisible", CONFTEST_USER_ID, fake_template_repo
    )

    # Grant share to user B directly in fake repo
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.get("/api/v1/templates", headers=auth_headers)
        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert str(tpl_id) in ids
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_shared_user_cannot_upload_new_version(
    async_client, app, auth_headers, fake_template_repo, monkeypatch, fake_template_engine
):
    """User B cannot upload a new version to a template they only have shared access to."""
    tpl_id = _upload_template_as_user(
        "SharedNoVersion", CONFTEST_USER_ID, fake_template_repo
    )
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    monkeypatch.setattr(
        "app.presentation.api.v1.templates.get_template_engine",
        lambda: fake_template_engine,
    )
    fake_template_engine.variables_to_return = ["name"]

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/versions",
            headers=auth_headers,
            files={
                "file": (
                    "template.docx",
                    io.BytesIO(b"fake-bytes"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_shared_user_cannot_delete_template(
    async_client, app, auth_headers, fake_template_repo
):
    """User B cannot delete a template they only have shared access to."""
    tpl_id = _upload_template_as_user(
        "SharedNoDelete", CONFTEST_USER_ID, fake_template_repo
    )
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="document_generator",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.delete(
            f"/api/v1/templates/{tpl_id}", headers=auth_headers
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_response_has_access_type_field(
    async_client, auth_headers, fake_template_repo
):
    """Template listing includes access_type field for each item."""
    # Admin user (conftest user) uploads — so access_type should be 'owned'
    _upload_template_as_user(
        "WithAccessType", CONFTEST_USER_ID, fake_template_repo
    )

    response = await async_client.get("/api/v1/templates", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    for item in items:
        assert "access_type" in item
        assert item["access_type"] in ("owned", "shared", "admin")


@pytest.mark.asyncio
async def test_admin_can_delete_any_template(
    async_client, app, auth_headers, fake_template_repo
):
    """Admin can delete a template owned by another user, and it disappears from the list."""
    # Seed a template owned by USER_B (not the admin test user)
    tpl_id = _upload_template_as_user(
        "AdminDeleteTarget", USER_B_ID, fake_template_repo
    )

    # The default test user (CONFTEST_USER_ID) has role "admin" per conftest
    response = await async_client.delete(
        f"/api/v1/templates/{tpl_id}", headers=auth_headers
    )
    assert response.status_code in (200, 204)

    # Verify the template is gone from the list (admin sees all)
    list_response = await async_client.get("/api/v1/templates", headers=auth_headers)
    assert list_response.status_code == 200
    ids = [item["id"] for item in list_response.json()["items"]]
    assert str(tpl_id) not in ids
