"""Integration tests — POST /api/v1/users/{user_id}/reset-password (admin password reset).

SCEN-PWRESET-01: template_creator calls endpoint → 403
SCEN-PWRESET-02: document_generator calls endpoint → 403
SCEN-PWRESET-03: admin resets password with valid data → 200, hash updated, reset tokens cleared
SCEN-PWRESET-04: admin resets password with new_password < 8 chars → 422
SCEN-PWRESET-05: admin resets password for non-existent user_id → 404
SCEN-PWRESET-06: audit log gets USER_PASSWORD_RESET_BY_ADMIN event with correct details
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.domain.entities import User
from app.domain.entities.audit_log import AuditAction
from app.infrastructure.auth.jwt_handler import hash_password, verify_password
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from tests.fakes import FakeUserRepository

# ── Stable IDs ────────────────────────────────────────────────────────────────

ADMIN_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ADMIN_TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TARGET_USER_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_user(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> User:
    return User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{role}_{user_id}@test.com",
        hashed_password=hash_password("original-password"),
        full_name=f"Test {role}",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        password_reset_token="stale-token",
        password_reset_sent_at=datetime.now(timezone.utc),
    )


def _make_repo_class(fake_repo: FakeUserRepository):
    """Return a drop-in replacement for SQLAlchemyUserRepository."""

    class _Repo:
        def __init__(self, session):  # noqa: ARG002
            self._fake = fake_repo

        async def get_by_id(self, user_id):
            return await self._fake.get_by_id(user_id)

        async def update(self, user_id, **kwargs):
            return await self._fake.update(user_id, **kwargs)

    return _Repo


def _seed_user(repo: FakeUserRepository, user: User) -> None:
    repo._users[user.id] = user
    repo._by_email[user.email] = user.id


# ── SCEN-PWRESET-01: template_creator → 403 ──────────────────────────────────


@pytest.mark.asyncio
async def test_template_creator_cannot_reset_password(async_client, app, auth_headers, monkeypatch):
    """SCEN-PWRESET-01: template_creator calling reset-password → 403."""
    non_admin = CurrentUser(
        user_id=uuid.uuid4(),
        tenant_id=ADMIN_TENANT_ID,
        role="template_creator",
    )

    async def override():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            f"/api/v1/users/{TARGET_USER_ID}/reset-password",
            headers=auth_headers,
            json={"new_password": "ValidPass1!"},
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── SCEN-PWRESET-02: document_generator → 403 ────────────────────────────────


@pytest.mark.asyncio
async def test_document_generator_cannot_reset_password(async_client, app, auth_headers, monkeypatch):
    """SCEN-PWRESET-02: document_generator calling reset-password → 403."""
    non_admin = CurrentUser(
        user_id=uuid.uuid4(),
        tenant_id=ADMIN_TENANT_ID,
        role="document_generator",
    )

    async def override():
        return non_admin

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = override
    try:
        response = await async_client.post(
            f"/api/v1/users/{TARGET_USER_ID}/reset-password",
            headers=auth_headers,
            json={"new_password": "ValidPass1!"},
        )
        assert response.status_code == 403, response.text
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ── SCEN-PWRESET-03: admin resets password → 200, hash updated, tokens cleared ─


@pytest.mark.asyncio
async def test_admin_resets_password_success(async_client, auth_headers, monkeypatch):
    """SCEN-PWRESET-03: Admin resets target user password → 200, hash updated, reset tokens cleared."""
    fake_repo = FakeUserRepository()
    target = _make_user(TARGET_USER_ID, ADMIN_TENANT_ID, "document_generator")
    assert target.password_reset_token == "stale-token"
    _seed_user(fake_repo, target)

    repo_class = _make_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        f"/api/v1/users/{TARGET_USER_ID}/reset-password",
        headers=auth_headers,
        json={"new_password": "NewSecure1!"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Password reset successfully"

    # Verify the hash was updated in the fake repo
    updated_user = fake_repo._users[TARGET_USER_ID]
    assert verify_password("NewSecure1!", updated_user.hashed_password)
    assert not verify_password("original-password", updated_user.hashed_password)

    # Verify the reset tokens were cleared
    assert updated_user.password_reset_token is None
    assert updated_user.password_reset_sent_at is None


# ── SCEN-PWRESET-04: new_password < 8 chars → 422 ───────────────────────────


@pytest.mark.asyncio
async def test_admin_reset_password_too_short_returns_422(async_client, auth_headers, monkeypatch):
    """SCEN-PWRESET-04: admin resets password with new_password < 8 chars → 422."""
    fake_repo = FakeUserRepository()
    target = _make_user(TARGET_USER_ID, ADMIN_TENANT_ID, "document_generator")
    _seed_user(fake_repo, target)

    repo_class = _make_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        f"/api/v1/users/{TARGET_USER_ID}/reset-password",
        headers=auth_headers,
        json={"new_password": "short"},  # 5 chars, < 8
    )
    assert response.status_code == 422, response.text


# ── SCEN-PWRESET-05: non-existent user_id → 404 ──────────────────────────────


@pytest.mark.asyncio
async def test_admin_reset_password_nonexistent_user_returns_404(async_client, auth_headers, monkeypatch):
    """SCEN-PWRESET-05: admin resets password for non-existent user_id → 404."""
    fake_repo = FakeUserRepository()  # empty repo — no users

    repo_class = _make_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    nonexistent_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    response = await async_client.post(
        f"/api/v1/users/{nonexistent_id}/reset-password",
        headers=auth_headers,
        json={"new_password": "ValidPass1!"},
    )
    assert response.status_code == 404, response.text


# ── SCEN-PWRESET-06: audit log gets USER_PASSWORD_RESET_BY_ADMIN event ────────


@pytest.mark.asyncio
async def test_admin_reset_password_logs_audit_event(async_client, auth_headers, monkeypatch):
    """SCEN-PWRESET-06: admin reset emits USER_PASSWORD_RESET_BY_ADMIN audit entry with correct details."""
    import asyncio
    from app.application.services.audit_service import AuditService
    from tests.fakes import FakeAuditRepository

    local_audit_repo = FakeAuditRepository()
    local_audit_service = AuditService(audit_repo=local_audit_repo)

    monkeypatch.setattr(
        "app.presentation.api.v1.users.get_audit_service",
        lambda: local_audit_service,
    )

    fake_repo = FakeUserRepository()
    target = _make_user(TARGET_USER_ID, ADMIN_TENANT_ID, "document_generator")
    _seed_user(fake_repo, target)

    repo_class = _make_repo_class(fake_repo)
    monkeypatch.setattr("app.presentation.api.v1.users.SQLAlchemyUserRepository", repo_class)

    response = await async_client.post(
        f"/api/v1/users/{TARGET_USER_ID}/reset-password",
        headers=auth_headers,
        json={"new_password": "AuditTest1!"},
    )
    assert response.status_code == 200, response.text

    # Give the fire-and-forget audit task a chance to run
    await asyncio.sleep(0.05)

    audit_entries = [
        e for e in local_audit_repo._entries
        if e.action == AuditAction.USER_PASSWORD_RESET_BY_ADMIN
    ]
    assert len(audit_entries) >= 1, f"Expected audit entry, got: {[e.action for e in local_audit_repo._entries]}"

    entry = audit_entries[0]
    assert entry.details is not None
    assert str(entry.details.get("actor_id")) == str(ADMIN_USER_ID)
    assert str(entry.details.get("target_user_id")) == str(TARGET_USER_ID)
