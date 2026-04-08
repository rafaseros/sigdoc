"""Unit tests for ConsoleEmailService and FakeEmailService.

Spec: SCEN-EMAIL-03, SCEN-EMAIL-04
"""

from __future__ import annotations

import pytest

from app.infrastructure.email.console_adapter import ConsoleEmailService
from tests.fakes.fake_email_service import FakeEmailService


# ── ConsoleEmailService ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_console_email_service_returns_true():
    """SCEN-EMAIL-03: ConsoleEmailService always returns True."""
    svc = ConsoleEmailService()
    result = await svc.send_email(
        to="user@example.com",
        subject="Test Subject",
        html_body="<p>Hello</p>",
        text_body="Hello",
    )
    assert result is True


@pytest.mark.asyncio
async def test_console_email_service_stores_email_in_list():
    """SCEN-EMAIL-03: ConsoleEmailService stores sent emails in sent_emails list."""
    svc = ConsoleEmailService()
    await svc.send_email(
        to="recipient@example.com",
        subject="Verificá tu correo",
        html_body="<p>Enlace: https://example.com</p>",
        text_body="Enlace: https://example.com",
    )
    assert len(svc.sent_emails) == 1
    assert svc.sent_emails[0].to == "recipient@example.com"
    assert svc.sent_emails[0].subject == "Verificá tu correo"


@pytest.mark.asyncio
async def test_console_email_service_accumulates_multiple_emails():
    """Multiple calls accumulate in sent_emails list."""
    svc = ConsoleEmailService()
    await svc.send_email("a@example.com", "Subject 1", "<p>1</p>")
    await svc.send_email("b@example.com", "Subject 2", "<p>2</p>")
    await svc.send_email("c@example.com", "Subject 3", "<p>3</p>")
    assert len(svc.sent_emails) == 3
    assert svc.sent_emails[1].to == "b@example.com"


# ── FakeEmailService ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fake_email_service_returns_true_by_default():
    """FakeEmailService returns True when should_fail=False (default)."""
    svc = FakeEmailService()
    result = await svc.send_email("user@test.com", "Subject", "<p>body</p>")
    assert result is True


@pytest.mark.asyncio
async def test_fake_email_service_captures_sent_email():
    """FakeEmailService captures sent email in sent list."""
    svc = FakeEmailService()
    await svc.send_email("user@test.com", "Hello", "<p>World</p>", "World")
    assert len(svc.sent) == 1
    assert svc.sent[0].to == "user@test.com"
    assert svc.sent[0].subject == "Hello"
    assert svc.sent[0].text_body == "World"


@pytest.mark.asyncio
async def test_fake_email_service_returns_false_when_configured_to_fail():
    """FakeEmailService returns False when should_fail=True."""
    svc = FakeEmailService(should_fail=True)
    result = await svc.send_email("user@test.com", "Subject", "<p>body</p>")
    assert result is False
    assert len(svc.sent) == 0  # Nothing stored on failure


@pytest.mark.asyncio
async def test_fake_email_service_clear_resets_list():
    """FakeEmailService.clear() empties the sent list."""
    svc = FakeEmailService()
    await svc.send_email("a@test.com", "S1", "<p>1</p>")
    await svc.send_email("b@test.com", "S2", "<p>2</p>")
    assert len(svc.sent) == 2
    svc.clear()
    assert len(svc.sent) == 0
