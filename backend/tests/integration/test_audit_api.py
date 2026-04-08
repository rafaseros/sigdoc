"""Integration tests — /api/v1/audit-log/* endpoints.

Strategy
--------
- FakeAuditRepository is session-scoped (shared state).  Tests that need
  a predictable starting state snapshot len(fake_audit_repo._entries) first
  and assert relative (delta) changes rather than absolute values.
- GET /audit-log uses Depends(get_audit_service) → our DI override intercepts.
- auth.py calls get_audit_service() directly (not via Depends), so the
  login-audit test monkeypatches the auth module's reference to return the fake.
- asyncio.create_task() in AuditService.log() is resolved with
  `await asyncio.sleep(0)` after each request.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.domain.entities import AuditAction
from app.infrastructure.auth.jwt_handler import hash_password
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeAuditRepository

# Conftest user constants (must match conftest.py)
CONFTEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONFTEST_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REGULAR_USER_ID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")

AUTH_TEST_EMAIL = "audit_test_user@example.com"
AUTH_TEST_PASSWORD = "verysecret99"
AUTH_TEST_USER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


# ── Unauthenticated ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_log_without_auth_returns_401(async_client, app):
    """GET /audit-log without a token must return 401."""
    original = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await async_client.get("/api/v1/audit-log")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original


# ── Authorization ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_log_as_regular_user_returns_403(async_client, app, auth_headers):
    """GET /audit-log as a non-admin user must return 403."""
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
        response = await async_client.get("/api/v1/audit-log", headers=auth_headers)
        assert response.status_code == 403
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_audit_log_as_admin_returns_200_paginated(async_client, auth_headers):
    """GET /audit-log as admin returns 200 with paginated structure."""
    response = await async_client.get("/api/v1/audit-log", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "size" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert data["page"] == 1
    assert data["size"] == 50  # default


@pytest.mark.asyncio
async def test_get_audit_log_pagination_params(async_client, auth_headers):
    """page and size query params are reflected in the response."""
    response = await async_client.get(
        "/api/v1/audit-log?page=2&size=5", headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["size"] == 5


@pytest.mark.asyncio
async def test_get_audit_log_size_capped_at_100(async_client, auth_headers):
    """size > 100 must return 422 (FastAPI validation)."""
    response = await async_client.get(
        "/api/v1/audit-log?size=101", headers=auth_headers
    )
    assert response.status_code == 422


# ── Action filter ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_action_returns_matching_entries(
    async_client,
    auth_headers,
    fake_audit_repo: FakeAuditRepository,
):
    """Filtering by action=document.generate returns only matching entries."""
    from app.domain.entities import AuditLog

    # Directly seed known entries into the fake repo
    before_count = len(fake_audit_repo._entries)

    target_action = AuditAction.DOCUMENT_GENERATE
    other_action = AuditAction.TEMPLATE_UPLOAD

    entry_target = AuditLog(
        id=uuid.uuid4(),
        tenant_id=CONFTEST_TENANT_ID,
        actor_id=CONFTEST_USER_ID,
        action=target_action,
        resource_type="document",
    )
    entry_other = AuditLog(
        id=uuid.uuid4(),
        tenant_id=CONFTEST_TENANT_ID,
        actor_id=CONFTEST_USER_ID,
        action=other_action,
        resource_type="template",
    )
    await fake_audit_repo.create(entry_target)
    await fake_audit_repo.create(entry_other)

    # Filter by target action
    response = await async_client.get(
        f"/api/v1/audit-log?action={target_action}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Every returned item must have the target action
    for item in data["items"]:
        assert item["action"] == target_action


# ── Audit record after document generation ───────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_has_entry_after_document_generation(
    async_client,
    auth_headers,
    fake_audit_repo: FakeAuditRepository,
    fake_template_repo,
    fake_storage,
):
    """After generating a document, an audit entry with document.generate appears."""
    from datetime import datetime, timezone
    from app.domain.entities import Template, TemplateVersion

    before_count = len(
        [e for e in fake_audit_repo._entries if e.action == AuditAction.DOCUMENT_GENERATE]
    )

    # Seed template
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
        variables=["name"],
        created_at=now,
    )
    template = Template(
        id=template_id,
        tenant_id=CONFTEST_TENANT_ID,
        name=f"AuditTest-{template_id}",
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

    # Generate a document
    gen_response = await async_client.post(
        "/api/v1/documents/generate",
        headers=auth_headers,
        json={"template_version_id": str(version_id), "variables": {"name": "Audit Bob"}},
    )
    assert gen_response.status_code == 201

    # Allow asyncio tasks (fire-and-forget audit writes) to complete
    await asyncio.sleep(0)

    after_count = len(
        [e for e in fake_audit_repo._entries if e.action == AuditAction.DOCUMENT_GENERATE]
    )
    assert after_count == before_count + 1


# ── Audit record after login ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_log_has_entry_after_login(
    async_client,
    fake_audit_repo: FakeAuditRepository,
    monkeypatch,
):
    """After a successful login, the fake audit repo records auth.login.

    auth.py calls get_audit_service() directly (not via DI), so we must
    monkeypatch that module-level reference to return an AuditService
    that writes to our fake_audit_repo.
    """
    from app.application.services.audit_service import AuditService

    # Build an AuditService backed by the integration fake repo
    audit_svc = AuditService(audit_repo=fake_audit_repo)

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.get_audit_service",
        lambda: audit_svc,
    )

    # Count auth.login entries before
    before_count = len(
        [e for e in fake_audit_repo._entries if e.action == AuditAction.AUTH_LOGIN]
    )

    # Seed a user into the auth module's repo (same pattern as test_auth_api.py)
    from app.domain.entities import User
    from tests.fakes import FakeUserRepository

    user = User(
        id=AUTH_TEST_USER_ID,
        tenant_id=CONFTEST_TENANT_ID,
        email=AUTH_TEST_EMAIL,
        hashed_password=hash_password(AUTH_TEST_PASSWORD),
        full_name="Audit Login User",
        role="user",
    )
    repo = FakeUserRepository()
    repo._users[user.id] = user
    repo._by_email[user.email] = user.id

    class _FakeRepo:
        def __init__(self, session):
            self._fake = repo

        async def get_by_email(self, email: str):
            return await self._fake.get_by_email(email)

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

    monkeypatch.setattr(
        "app.presentation.api.v1.auth.SQLAlchemyUserRepository",
        _FakeRepo,
    )

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": AUTH_TEST_EMAIL, "password": AUTH_TEST_PASSWORD},
    )
    assert response.status_code == 200

    # Allow asyncio.create_task() to complete
    await asyncio.sleep(0)

    after_count = len(
        [e for e in fake_audit_repo._entries if e.action == AuditAction.AUTH_LOGIN]
    )
    assert after_count == before_count + 1
