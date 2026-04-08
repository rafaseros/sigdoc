"""Integration tests — /api/v1/templates/{id}/shares endpoints (task 5.6).

Tests cover:
- POST /templates/{id}/shares — owner shares (201)
- POST /templates/{id}/shares — non-owner gets 403
- DELETE /templates/{id}/shares/{user_id} — owner unshares (204)
- GET /templates/{id}/shares — owner sees share list (200)
- Non-owner trying to manage shares → 403
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import Template, TemplateVersion
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeTemplateRepository

# Stable IDs from integration conftest
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

# A regular user (non-owner) used for 403 tests
USER_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


# ── Helpers ───────────────────────────────────────────────────────────────────


def seed_template(
    owner_id: uuid.UUID,
    fake_template_repo: FakeTemplateRepository,
    name: str = "ShareTestTemplate",
) -> uuid.UUID:
    """Seed a Template directly in the fake repo. Returns template_id."""
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
        name=name,
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


# ── POST /templates/{id}/shares ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_share_template(
    async_client, auth_headers, fake_template_repo
):
    """Owner shares their template — response is 201 with share details."""
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "Shareable")
    target_user_id = uuid.uuid4()

    response = await async_client.post(
        f"/api/v1/templates/{tpl_id}/shares",
        headers=auth_headers,
        json={"user_id": str(target_user_id)},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["template_id"] == str(tpl_id)
    assert data["user_id"] == str(target_user_id)
    assert "id" in data
    assert "shared_by" in data


@pytest.mark.asyncio
async def test_non_owner_cannot_share_template(
    async_client, app, auth_headers, fake_template_repo
):
    """Non-owner (user B) gets 403 when trying to share user A's template."""
    # Template is owned by CONFTEST_USER_ID (admin), user B has no relation
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "NonOwnerShare")
    target_user_id = uuid.uuid4()

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.post(
            f"/api/v1/templates/{tpl_id}/shares",
            headers=auth_headers,
            json={"user_id": str(target_user_id)},
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_duplicate_share_is_idempotent(
    async_client, auth_headers, fake_template_repo
):
    """Sharing the same user twice does not error — returns existing share."""
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "IdempotentShare")
    target_user_id = uuid.uuid4()

    r1 = await async_client.post(
        f"/api/v1/templates/{tpl_id}/shares",
        headers=auth_headers,
        json={"user_id": str(target_user_id)},
    )
    assert r1.status_code == 201

    r2 = await async_client.post(
        f"/api/v1/templates/{tpl_id}/shares",
        headers=auth_headers,
        json={"user_id": str(target_user_id)},
    )
    # Idempotent — should not 409
    assert r2.status_code in (200, 201)

    # Only one share record should exist
    shares = await fake_template_repo.list_shares(tpl_id)
    user_shares = [s for s in shares if s.user_id == target_user_id]
    assert len(user_shares) == 1


# ── DELETE /templates/{id}/shares/{user_id} ───────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_unshare_template(
    async_client, auth_headers, fake_template_repo
):
    """Owner can revoke a share — response is 204."""
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "Unshareable")
    shared_user_id = uuid.uuid4()

    # Share first
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=shared_user_id,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    response = await async_client.delete(
        f"/api/v1/templates/{tpl_id}/shares/{shared_user_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Confirm share is gone
    has_access = await fake_template_repo.has_access(tpl_id, shared_user_id, "user")
    assert has_access is False


@pytest.mark.asyncio
async def test_non_owner_cannot_unshare_template(
    async_client, app, auth_headers, fake_template_repo
):
    """Non-owner (user B) gets 403 when trying to unshare a template."""
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "NonOwnerUnshare")
    shared_user_id = uuid.uuid4()

    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=shared_user_id,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.delete(
            f"/api/v1/templates/{tpl_id}/shares/{shared_user_id}",
            headers=auth_headers,
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── GET /templates/{id}/shares ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_owner_can_list_shares(
    async_client, auth_headers, fake_template_repo
):
    """Owner can list all shares for their template — response is 200 with share list."""
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "ListShares")
    shared_user_1 = uuid.uuid4()
    shared_user_2 = uuid.uuid4()

    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=shared_user_1,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )
    await fake_template_repo.add_share(
        template_id=tpl_id,
        user_id=shared_user_2,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    response = await async_client.get(
        f"/api/v1/templates/{tpl_id}/shares",
        headers=auth_headers,
    )

    assert response.status_code == 200
    shares = response.json()
    assert isinstance(shares, list)
    assert len(shares) == 2
    user_ids_in_response = {s["user_id"] for s in shares}
    assert str(shared_user_1) in user_ids_in_response
    assert str(shared_user_2) in user_ids_in_response


@pytest.mark.asyncio
async def test_non_owner_cannot_list_shares(
    async_client, app, auth_headers, fake_template_repo
):
    """User B (no relation to template) gets 403 trying to list shares.

    The service's list_template_shares calls _check_access with require_owner=False,
    so any user with access can list shares. A user with NO access gets 403.
    User B has neither ownership nor a share, so they get 403.
    """
    # Template owned by CONFTEST_USER_ID; user B has NO share
    tpl_id = seed_template(CONFTEST_USER_ID, fake_template_repo, "ListSharesDenied")

    user_b = CurrentUser(
        user_id=USER_B_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_user_b():
        return user_b

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_user_b
    try:
        response = await async_client.get(
            f"/api/v1/templates/{tpl_id}/shares",
            headers=auth_headers,
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)
