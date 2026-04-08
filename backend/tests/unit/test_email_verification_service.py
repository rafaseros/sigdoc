"""Unit tests for EmailVerificationService.

Spec: SCEN-VERIFY-01 through SCEN-VERIFY-07
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.application.services.email_verification_service import EmailVerificationService
from app.domain.entities.user import User
from app.infrastructure.auth.jwt_handler import hash_password
from tests.fakes.fake_email_service import FakeEmailService
from tests.fakes.fake_user_repository import FakeUserRepository


def _make_user(
    *,
    email_verified: bool = False,
    token: str | None = None,
    sent_at: datetime | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="user@example.com",
        hashed_password=hash_password("secret"),
        full_name="Test User",
        role="user",
        is_active=True,
        email_verified=email_verified,
        email_verification_token=token,
        email_verification_sent_at=sent_at,
    )
    return user


# ── SCEN-VERIFY-01: Send verification email ────────────────────────────────────


@pytest.mark.asyncio
async def test_send_verification_generates_token_and_queues_email():
    """SCEN-VERIFY-01: send_verification stores token and fires email."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()
    user = _make_user()
    await fake_repo.create(user)

    await EmailVerificationService.send_verification(
        user=user,
        email_service=fake_email,
        user_repo=fake_repo,
        frontend_url="http://localhost:5173",
    )

    # Flush pending tasks so fire-and-forget email is sent
    await asyncio.sleep(0)

    updated_user = await fake_repo.get_by_id(user.id)
    assert updated_user.email_verification_token is not None
    assert len(updated_user.email_verification_token) == 64  # 32 bytes hex
    assert len(fake_email.sent) == 1
    assert fake_email.sent[0].to == user.email
    assert "verify-email" in fake_email.sent[0].html_body


# ── SCEN-VERIFY-02: Verify valid token ────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_valid_token_marks_user_as_verified():
    """SCEN-VERIFY-02: Valid token → email_verified=True, token cleared."""
    fake_repo = FakeUserRepository()
    token = "a" * 64
    user = _make_user(
        token=token,
        sent_at=datetime.now(timezone.utc),
    )
    await fake_repo.create(user)

    ok, reason = await EmailVerificationService.verify_token(
        token=token,
        user_repo=fake_repo,
    )

    assert ok is True
    assert reason == ""
    updated = await fake_repo.get_by_id(user.id)
    assert updated.email_verified is True
    assert updated.email_verification_token is None


# ── SCEN-VERIFY-03: Invalid token ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_invalid_token_returns_false():
    """SCEN-VERIFY-03: Unknown token → (False, error message)."""
    fake_repo = FakeUserRepository()

    ok, reason = await EmailVerificationService.verify_token(
        token="nonexistent-token",
        user_repo=fake_repo,
    )

    assert ok is False
    assert "válido" in reason


# ── SCEN-VERIFY-04: Expired token ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_expired_token_returns_false():
    """SCEN-VERIFY-04: Token older than 24h → (False, expired message)."""
    fake_repo = FakeUserRepository()
    token = "b" * 64
    old_sent_at = datetime.now(timezone.utc) - timedelta(hours=25)  # expired
    user = _make_user(token=token, sent_at=old_sent_at)
    await fake_repo.create(user)

    ok, reason = await EmailVerificationService.verify_token(
        token=token,
        user_repo=fake_repo,
    )

    assert ok is False
    assert "expirado" in reason


# ── SCEN-VERIFY-05: Already verified (idempotent) ─────────────────────────────


@pytest.mark.asyncio
async def test_verify_already_verified_user_returns_true():
    """SCEN-VERIFY-05: Already verified user → (True, "") — idempotent."""
    fake_repo = FakeUserRepository()
    token = "c" * 64
    user = _make_user(email_verified=True, token=token, sent_at=datetime.now(timezone.utc))
    await fake_repo.create(user)

    ok, reason = await EmailVerificationService.verify_token(
        token=token,
        user_repo=fake_repo,
    )

    assert ok is True
    assert reason == ""


# ── SCEN-VERIFY-06: Resend verification ───────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_verification_for_unverified_user():
    """SCEN-VERIFY-06: Resend generates new token and sends email."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()
    old_token = "d" * 64
    user = _make_user(
        email_verified=False,
        token=old_token,
        sent_at=datetime.now(timezone.utc),
    )
    await fake_repo.create(user)

    ok, reason = await EmailVerificationService.resend_verification(
        user=user,
        email_service=fake_email,
        user_repo=fake_repo,
        frontend_url="http://localhost:5173",
    )

    await asyncio.sleep(0)  # flush tasks

    assert ok is True
    assert reason == ""

    updated = await fake_repo.get_by_id(user.id)
    # New token should differ from old
    assert updated.email_verification_token is not None
    assert updated.email_verification_token != old_token


# ── SCEN-VERIFY-07: Resend for already verified user ─────────────────────────


@pytest.mark.asyncio
async def test_resend_verification_for_verified_user_returns_false():
    """SCEN-VERIFY-07: Already verified user → (False, already verified)."""
    fake_repo = FakeUserRepository()
    fake_email = FakeEmailService()
    user = _make_user(email_verified=True)
    await fake_repo.create(user)

    ok, reason = await EmailVerificationService.resend_verification(
        user=user,
        email_service=fake_email,
        user_repo=fake_repo,
    )

    assert ok is False
    assert "verificado" in reason
    assert len(fake_email.sent) == 0
