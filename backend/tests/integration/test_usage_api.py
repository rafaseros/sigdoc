"""Integration tests — /api/v1/usage/* endpoints.

Strategy
--------
- FakeUsageRepository is session-scoped (shared state across tests).
  Tests that need isolated counts clear the repo before acting or
  snapshot the current total and assert relative changes (delta).
- The conftest admin user (role="admin") is the default auth identity.
- Non-admin scenario is simulated by temporarily swapping get_current_user.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.domain.entities import Template, TemplateVersion
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeStorageService, FakeTemplateRepository, FakeUsageRepository

from datetime import datetime, timezone

# Conftest user constants
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

REGULAR_USER_ID = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


def _seed_template_version(
    fake_template_repo: FakeTemplateRepository,
    fake_storage: FakeStorageService,
    variables: list[str] | None = None,
) -> str:
    """Seed a Template + TemplateVersion accessible to the conftest admin user."""
    if variables is None:
        variables = ["name"]

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
        name=f"UsageTest-{template_id}",
        description=None,
        current_version=1,
        created_by=CONFTEST_USER_ID,
        versions=[version],
        created_at=now,
        updated_at=now,
    )
    fake_template_repo._templates[template_id] = template
    fake_template_repo._versions[version_id] = version
    fake_storage.files[("templates", minio_path)] = b"fake-docx-bytes"

    return str(version_id)


# ── Unauthenticated ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_usage_without_auth_returns_401(async_client, app):
    """GET /usage without a token must return 401."""
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/usage")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Authenticated — own stats ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_usage_with_auth_returns_200_and_correct_shape(async_client, auth_headers):
    """GET /usage returns 200 with the required fields."""
    response = await async_client.get("/api/v1/usage", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "user_id" in data
    assert "year" in data
    assert "month" in data
    assert "total_documents" in data
    assert "by_template" in data
    assert isinstance(data["total_documents"], int)
    assert isinstance(data["by_template"], list)


@pytest.mark.asyncio
async def test_get_usage_with_explicit_year_month_returns_422_for_invalid(
    async_client, auth_headers
):
    """year/month out of range must return 422 (FastAPI validation)."""
    response = await async_client.get(
        "/api/v1/usage?year=1999&month=1", headers=auth_headers
    )
    assert response.status_code == 422

    response = await async_client.get(
        "/api/v1/usage?year=2025&month=13", headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_usage_after_document_generation_increments_count(
    async_client,
    app,
    auth_headers,
    fake_template_repo,
    fake_storage,
    fake_usage_repo,
):
    """After generating a document, GET /usage shows an incremented total."""
    # Snapshot current total before generating
    from datetime import date

    today = date.today()
    before = await fake_usage_repo.get_user_month_total(
        user_id=CONFTEST_USER_ID,
        month_start=date(today.year, today.month, 1),
    )

    # Seed a template and generate a document
    version_id = _seed_template_version(fake_template_repo, fake_storage, ["name"])
    gen_response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={"template_version_id": version_id, "variables": {"name": "Delta Test"}},
    )
    assert gen_response.status_code == 201

    # GET /usage — total must be before + 1
    response = await async_client.get(
        f"/api/v1/usage?year={today.year}&month={today.month}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_documents"] == before + 1
    assert data["year"] == today.year
    assert data["month"] == today.month


# ── Tenant endpoint — admin vs non-admin ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_tenant_usage_as_admin_returns_200(async_client, auth_headers):
    """GET /usage/tenant as admin → 200."""
    response = await async_client.get("/api/v1/usage/tenant", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "tenant_id" in data
    assert "year" in data
    assert "month" in data
    assert "total_documents" in data
    assert "by_user" in data
    assert isinstance(data["by_user"], list)


@pytest.mark.asyncio
async def test_get_tenant_usage_as_regular_user_returns_403(async_client, app, auth_headers):
    """GET /usage/tenant as non-admin → 403."""
    regular_user = CurrentUser(
        user_id=REGULAR_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        role="user",
    )

    async def override_as_regular():
        return regular_user

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override_as_regular
    try:
        response = await async_client.get("/api/v1/usage/tenant", headers=auth_headers)
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_tenant_usage_without_auth_returns_401(async_client, app):
    """GET /usage/tenant without token → 401."""
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/usage/tenant")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
