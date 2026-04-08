"""Unit tests for PasswordResetService.

Spec: SCEN-RESET-01 through SCEN-RESET-06
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.password_reset_service import PasswordResetService
from app.domain.entities.user import User
from app.infrastructure.auth.jwt_handler import hash_password, verify_password
from tests.fakes.fake_email_service import FakeEmailService
from tests.fakes.fake_user_repository import FakeUserRepository


def _make_user(
    *,
    reset_token: str | None = None,
    reset_sent_at: datetime | None = None,
) -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="user@example.com",
        hashed_password=hash_password("original-password"),
        full_name="Test User",
        role="user",
        is_active=True,
        password_reset_token=reset_token,
        password_reset_sent_at=reset_sent_at,
    )


# ── SCEN-RESET-01: Request reset for existing user ────────────────────────────


@pytest.mark.asyncio
async def test_request_reset_for_existing_user_sends_email():
    """SCEN-RESET-01: request_reset stores token and sends email."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()
    user = _make_user()
    await fake_repo.create(user)

    await PasswordResetService.request_reset(
        email=user.email,
        email_service=fake_email,
        user_repo=fake_repo,
        frontend_url="http://localhost:5173",
    )

    await asyncio.sleep(0)  # flush tasks

    updated = await fake_repo.get_by_id(user.id)
    assert updated.password_reset_token is not None
    assert len(updated.password_reset_token) == 64  # 32 bytes hex
    assert len(fake_email.sent) == 1
    assert fake_email.sent[0].to == user.email
    assert "reset-password" in fake_email.sent[0].html_body


# ── SCEN-RESET-02: Request reset for non-existent user — silent ──────────────


@pytest.mark.asyncio
async def test_request_reset_for_nonexistent_user_does_nothing():
    """SCEN-RESET-02: Non-existent email → no email sent, no error raised (anti-enumeration)."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()

    # Should not raise
    await PasswordResetService.request_reset(
        email="nobody@example.com",
        email_service=fake_email,
        user_repo=fake_repo,
    )

    await asyncio.sleep(0)
    assert len(fake_email.sent) == 0


# ── SCEN-RESET-03: Reset with valid token ────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_updates_password():
    """SCEN-RESET-03: Valid token → password updated, token cleared."""
    fake_repo = FakeUserRepository()
    token = "a" * 64
    user = _make_user(reset_token=token, reset_sent_at=datetime.now(timezone.utc))
    await fake_repo.create(user)

    ok, reason = await PasswordResetService.reset_password(
        token=token,
        new_password="newpassword123",
        user_repo=fake_repo,
    )

    assert ok is True
    assert reason == ""

    updated = await fake_repo.get_by_id(user.id)
    assert updated.password_reset_token is None
    # New password should verify
    assert verify_password("newpassword123", updated.hashed_password)


# ── SCEN-RESET-04: Reset with invalid token ───────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token_returns_false():
    """SCEN-RESET-04: Unknown token → (False, error message)."""
    fake_repo = FakeUserRepository()

    ok, reason = await PasswordResetService.reset_password(
        token="nonexistent-token",
        new_password="newpassword123",
        user_repo=fake_repo,
    )

    assert ok is False
    assert "válido" in reason


# ── SCEN-RESET-05: Reset with expired token ───────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_with_expired_token_returns_false():
    """SCEN-RESET-05: Token older than 1 hour → (False, expired message)."""
    fake_repo = FakeUserRepository()
    token = "b" * 64
    old_sent_at = datetime.now(timezone.utc) - timedelta(hours=2)  # expired
    user = _make_user(reset_token=token, reset_sent_at=old_sent_at)
    await fake_repo.create(user)

    ok, reason = await PasswordResetService.reset_password(
        token=token,
        new_password="newpassword123",
        user_repo=fake_repo,
    )

    assert ok is False
    assert "expirado" in reason


# ── SCEN-RESET-06: Reset is one-time use ─────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_token_is_cleared_after_use():
    """SCEN-RESET-06: After successful reset, token cannot be reused."""
    fake_repo = FakeUserRepository()
    token = "c" * 64
    user = _make_user(reset_token=token, reset_sent_at=datetime.now(timezone.utc))
    await fake_repo.create(user)

    # First use — succeeds
    ok1, _ = await PasswordResetService.reset_password(
        token=token,
        new_password="newpassword123",
        user_repo=fake_repo,
    )
    assert ok1 is True

    # Second use — token is cleared, should fail
    ok2, reason = await PasswordResetService.reset_password(
        token=token,
        new_password="anotherpassword",
        user_repo=fake_repo,
    )
    assert ok2 is False
    assert "válido" in reason


# ── SCEN-RESET-07: New request overwrites old token ──────────────────────────


@pytest.mark.asyncio
async def test_new_reset_request_overwrites_old_token():
    """SCEN-RESET-07: Second request_reset replaces the first token."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()
    user = _make_user()
    await fake_repo.create(user)

    # First request
    await PasswordResetService.request_reset(
        email=user.email,
        email_service=fake_email,
        user_repo=fake_repo,
    )
    await asyncio.sleep(0)

    user_after_first = await fake_repo.get_by_id(user.id)
    first_token = user_after_first.password_reset_token
    assert first_token is not None

    # Second request
    await PasswordResetService.request_reset(
        email=user.email,
        email_service=fake_email,
        user_repo=fake_repo,
    )
    await asyncio.sleep(0)

    user_after_second = await fake_repo.get_by_id(user.id)
    second_token = user_after_second.password_reset_token
    assert second_token is not None
    # New token should differ from the old one
    assert second_token != first_token
