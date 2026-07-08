"""Integration tests — /api/v1/templates/{tid}/presets endpoints.

Access rule for ALL preset operations: template ACCESS (owner,
shared-with-user, or admin) — same as GET /templates/{id}. Presets are
shared by everyone with access to the template (explicit product decision).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeTemplateRepository

CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
USER_B_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _seed_template(
    fake_template_repo: FakeTemplateRepository,
    owner_id: uuid.UUID,
    name: str = "PresetTestTemplate",
) -> uuid.UUID:
    template_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=name,
        description=None,
        current_version=1,
        created_by=owner_id,
        versions=[],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    return template_id


async def _as_user_b(app):
    """Context manager-less helper: swap get_current_user override to
    USER_B_ID for the duration of the caller's block, restoring afterward."""
    user_b = CurrentUser(
        user_id=USER_B_ID, tenant_id=CONFTEST_TENANT_ID, role="document_generator"
    )

    async def override():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    return original


def _restore_user(app, original):
    if original is not None:
        app.dependency_overrides[get_current_user] = original
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_owner_can_create_list_and_get_preset(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetCreateListOwner")

    create_response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Cliente Frecuente", "values": {"nombre": "Acme"}},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Cliente Frecuente"
    assert created["values"] == {"nombre": "Acme"}
    assert "created_at" in created

    list_response = await async_client.get(
        f"/api/v1/templates/{template_id}/presets", headers=auth_headers
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert len(data["presets"]) == 1
    assert data["presets"][0]["name"] == "Cliente Frecuente"


@pytest.mark.asyncio
async def test_presets_ordered_by_name(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetOrdered")

    for name in ["Zeta", "Alpha", "Mid"]:
        response = await async_client.post(
            f"/api/v1/templates/{template_id}/presets",
            headers=auth_headers,
            json={"name": name, "values": {}},
        )
        assert response.status_code == 201

    list_response = await async_client.get(
        f"/api/v1/templates/{template_id}/presets", headers=auth_headers
    )
    names = [p["name"] for p in list_response.json()["presets"]]
    assert names == ["Alpha", "Mid", "Zeta"]


@pytest.mark.asyncio
async def test_shared_user_can_create_preset(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    """Explicit product decision: a shared user (document_generator) can
    create presets on a template they have access to, not just the owner."""
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetSharedCreate")
    await fake_template_repo.add_share(
        template_id=template_id,
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    original = await _as_user_b(app)
    try:
        response = await async_client.post(
            f"/api/v1/templates/{template_id}/presets",
            headers=auth_headers,
            json={"name": "Preset De B", "values": {"x": "y"}},
        )
        assert response.status_code == 201
        assert response.json()["created_by"] == str(USER_B_ID)
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_unrelated_user_gets_403(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    """A user with no access to the template (not owner, not shared) is
    denied — no admin override in this scenario since USER_B has role
    document_generator with no share record."""
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetUnrelated")

    original = await _as_user_b(app)
    try:
        response = await async_client.post(
            f"/api/v1/templates/{template_id}/presets",
            headers=auth_headers,
            json={"name": "No Deberia", "values": {}},
        )
        assert response.status_code == 403
    finally:
        _restore_user(app, original)


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetDuplicate")

    first = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Repetido", "values": {}},
    )
    assert first.status_code == 201

    second = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Repetido", "values": {}},
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_create_with_non_string_value_returns_422(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetBadValues")

    response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Malformado", "values": {"a": 1}},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_for_unknown_template_returns_404(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    response = await async_client.post(
        f"/api/v1/templates/{uuid.uuid4()}/presets",
        headers=auth_headers,
        json={"name": "Fantasma", "values": {}},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_owner_can_update_preset_name_and_values(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetUpdateOwner")
    create_response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Original", "values": {"a": "1"}},
    )
    preset_id = create_response.json()["id"]

    update_response = await async_client.patch(
        f"/api/v1/templates/{template_id}/presets/{preset_id}",
        headers=auth_headers,
        json={"name": "Renombrado", "values": {"a": "2"}},
    )
    assert update_response.status_code == 200
    data = update_response.json()
    assert data["name"] == "Renombrado"
    assert data["values"] == {"a": "2"}


@pytest.mark.asyncio
async def test_update_with_empty_body_returns_422(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetEmptyBody")
    create_response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Original", "values": {}},
    )
    preset_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/templates/{template_id}/presets/{preset_id}",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_with_null_values_returns_422(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    """values is NOT NULL in the DB — explicit null must be rejected at the
    schema level (422), not surface as a misleading 409 name-collision
    error from a caught IntegrityError."""
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetNullValues")
    create_response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Original", "values": {"a": "1"}},
    )
    preset_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/templates/{template_id}/presets/{preset_id}",
        headers=auth_headers,
        json={"values": None},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_unknown_preset_returns_404(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetUpdateUnknown")

    response = await async_client.patch(
        f"/api/v1/templates/{template_id}/presets/{uuid.uuid4()}",
        headers=auth_headers,
        json={"name": "X"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_preset_from_foreign_template_returns_404_non_leaking(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id_1 = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetForeign1")
    template_id_2 = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetForeign2")

    create_response = await async_client.post(
        f"/api/v1/templates/{template_id_1}/presets",
        headers=auth_headers,
        json={"name": "Solo En Uno", "values": {}},
    )
    preset_id = create_response.json()["id"]

    response = await async_client.patch(
        f"/api/v1/templates/{template_id_2}/presets/{preset_id}",
        headers=auth_headers,
        json={"name": "Intento"},
    )
    assert response.status_code == 404
    assert "Solo En Uno" not in response.text


@pytest.mark.asyncio
async def test_update_rename_to_duplicate_returns_409(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetUpdateDup")
    await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Existente", "values": {}},
    )
    second = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Otro", "values": {}},
    )
    preset_id = second.json()["id"]

    response = await async_client.patch(
        f"/api/v1/templates/{template_id}/presets/{preset_id}",
        headers=auth_headers,
        json={"name": "Existente"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_delete_preset(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetDelete")
    create_response = await async_client.post(
        f"/api/v1/templates/{template_id}/presets",
        headers=auth_headers,
        json={"name": "Borrame", "values": {}},
    )
    preset_id = create_response.json()["id"]

    delete_response = await async_client.delete(
        f"/api/v1/templates/{template_id}/presets/{preset_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    list_response = await async_client.get(
        f"/api/v1/templates/{template_id}/presets", headers=auth_headers
    )
    assert list_response.json()["presets"] == []


@pytest.mark.asyncio
async def test_delete_unknown_preset_returns_404(
    async_client, app, auth_headers, fake_template_repo: FakeTemplateRepository
):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetDeleteUnknown")

    response = await async_client.delete(
        f"/api/v1/templates/{template_id}/presets/{uuid.uuid4()}",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(async_client, app, fake_template_repo):
    template_id = _seed_template(fake_template_repo, CONFTEST_USER_ID, "PresetUnauth")

    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get(f"/api/v1/templates/{template_id}/presets")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
