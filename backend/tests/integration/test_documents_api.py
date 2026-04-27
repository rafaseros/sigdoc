"""Integration tests — /api/v1/documents/* endpoints.

Uses the fakes wired in integration conftest.  Before each test that calls
generate, we seed a TemplateVersion into the shared FakeTemplateRepository
and the corresponding template bytes into FakeStorageService.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from unittest.mock import AsyncMock, MagicMock

from app.domain.entities import Template, TemplateVersion, User
from app.infrastructure.auth.jwt_handler import hash_password
from app.infrastructure.persistence.database import get_session
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeStorageService, FakeTemplateRepository, FakeUserRepository

# ── Helpers ───────────────────────────────────────────────────────────────────

CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

# A user with no relation to templates seeded by the conftest user
UNRELATED_USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SHARED_USER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


def seed_template_version(
    fake_template_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    variables: list[str] | None = None,
    owner_id: uuid.UUID | None = None,
) -> str:
    """Seed a Template + TemplateVersion in the fake repo and fake storage.

    The Template is seeded so that has_access() returns True for the owner.
    Returns the version_id as a string.
    """
    if variables is None:
        variables = ["name", "date"]

    if owner_id is None:
        owner_id = CONFTEST_USER_ID

    template_id = uuid.uuid4()
    version_id = uuid.uuid4()
    minio_path = f"{CONFTEST_TENANT_ID}/{template_id}/v1/template.docx"
    now = datetime.now(timezone.utc)

    version = TemplateVersion(
        id=version_id,
        tenant_id=CONFTEST_TENANT_ID,
        template_id=template_id,
        version=1,
        minio_path=minio_path,
        variables=variables,
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=f"TestTemplate-{template_id}",
        description=None,
        current_version=1,
        created_by=owner_id,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = b"fake-docx-bytes"

    return str(version_id)


# ── Unauthenticated requests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_without_auth_returns_401(async_client, app):
    from app.presentation.middleware.tenant import get_current_user

    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            json={"template_version_id": str(uuid.uuid4()), "variables": {}},
        )
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Authenticated generate ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_with_valid_version_returns_201(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    version_id = seed_template_version(fake_template_repo, fake_storage, ["name", "date"])

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "date": "2025-01-01"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "download_url" in data
    assert data["generation_type"] == "single"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_download_url_is_present(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    version_id = seed_template_version(fake_template_repo, fake_storage)

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Bob", "date": "2025-06-01"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["download_url"] is not None
    assert f"/documents/" in data["download_url"]


@pytest.mark.asyncio
async def test_generate_with_unknown_version_returns_404(
    async_client, auth_headers
):
    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": str(uuid.uuid4()),
            "variables": {"name": "Alice"},
        },
    )

    assert response.status_code == 404


# ── Task 5.7: Template access check tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_unrelated_user_cannot_generate_from_private_template(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """User with no relation to the template gets 403 when generating."""
    # Template owned by conftest admin user; unrelated user has no access
    version_id = seed_template_version(
        fake_template_repo, fake_storage, owner_id=CONFTEST_USER_ID
    )

    unrelated_user = CurrentUser(
        user_id=UNRELATED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_unrelated():
        return unrelated_user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_unrelated
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": version_id,
                "variables": {"name": "Eve", "date": "2025-01-01"},
            },
        )
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_shared_user_can_generate_from_shared_template(
    async_client, app, auth_headers, fake_template_repo, fake_storage
):
    """User with an explicit share record can generate documents — returns 201."""
    version_id = seed_template_version(
        fake_template_repo, fake_storage, owner_id=CONFTEST_USER_ID
    )

    # Get the template_id for this version
    version_uuid = uuid.UUID(version_id)
    version = fake_template_repo._versions[version_uuid]

    # Grant share to SHARED_USER_ID
    await fake_template_repo.add_share(
        template_id=version.template_id,
        user_id=SHARED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        shared_by=CONFTEST_USER_ID,
    )

    shared_user = CurrentUser(
        user_id=SHARED_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_shared():
        return shared_user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_shared
    try:
        response = await async_client.post(
            "/api/v1/documents/generate",
            headers=auth_headers,
            json={
                "template_version_id": version_id,
                "variables": {"name": "Bob", "date": "2025-06-01"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "completed"
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── REQ-SOS-13: No email-verification gate on generate ───────────────────────
# T-VERIFY-15 (SCEN-VERIFY-04 / SCEN-VERIFY-05) removed: _require_verified_email
# is being deleted per single-org-cutover. Tests below assert the gate is GONE.


@pytest.mark.asyncio
async def test_document_generate_works_for_unverified_user(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """REQ-SOS-13 / SCEN-SOS-12: User with email_verified=False MUST get 201 (no gate).

    RED: currently fails with 403 because _require_verified_email still exists.
    GREEN: passes after _require_verified_email is removed from the handler.
    """
    version_id = seed_template_version(fake_template_repo, fake_storage, ["name", "date"])

    # The conftest already wires an unverified-friendly user via get_current_user override.
    # We confirm the endpoint accepts any authenticated user regardless of email_verified.
    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "UnverifiedAlice", "date": "2025-01-01"},
        },
    )
    assert response.status_code == 201, (
        f"Expected 201 (no email-verification gate), got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_document_generate_bulk_works_for_unverified_user(
    async_client, auth_headers, fake_template_repo, fake_storage
):
    """REQ-SOS-13 (bulk): Unverified user MUST succeed on generate-bulk (no gate).

    Triangulation: second endpoint confirms _require_verified_email is gone from
    both generate and generate-bulk.
    """
    import io
    import openpyxl

    version_id = seed_template_version(fake_template_repo, fake_storage, ["name", "date"])

    # Build a minimal valid .xlsx with one data row
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "date"])  # header row
    ws.append(["Bob", "2025-06-01"])  # data row
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = await async_client.post(
        "/api/v1/documents/generate-bulk",
        headers=auth_headers,
        data={"template_version_id": version_id},
        files={"file": ("data.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 201, (
        f"Expected 201 (no email-verification gate on bulk), got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_generate_document_blocked_for_unverified_user(
    async_client, app, auth_headers, fake_template_repo, fake_storage, monkeypatch
):
    """SCEN-VERIFY-04: kept as historical marker — NOW EXPECTS 201 (gate removed).

    After _require_verified_email is deleted, unverified users are no longer blocked.
    This replaces the old 403 assertion with the new 201 expectation.
    """
    version_id = seed_template_version(fake_template_repo, fake_storage, ["name", "date"])

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "date": "2025-01-01"},
        },
    )
    # Gate is gone — unverified user gets through to normal processing
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_generate_document_allowed_for_verified_user(
    async_client, app, auth_headers, fake_template_repo, fake_storage, monkeypatch
):
    """SCEN-VERIFY-05: Verified user can still generate documents normally."""
    version_id = seed_template_version(fake_template_repo, fake_storage, ["name", "date"])

    response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={
            "template_version_id": version_id,
            "variables": {"name": "Alice", "date": "2025-01-01"},
        },
    )
    assert response.status_code == 201, response.text


