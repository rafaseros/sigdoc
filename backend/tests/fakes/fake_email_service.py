"""FakeEmailService — in-memory email service for testing.

Stores all sent emails in a list so tests can assert what was sent.
Can be configured to fail (return False) for negative-path testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.ports.email_service import EmailService


@dataclass
class CapturedEmail:
    """A single email captured by FakeEmailService."""
    to: str
    subject: str
    html_body: str
    text_body: str


class FakeEmailService(EmailService):
    """In-memory email service for tests.

    Usage:
        fake = FakeEmailService()
        # ... code that sends email ...
        assert len(fake.sent) == 1
        assert fake.sent[0].to == "user@example.com"

    To simulate failure:
        fake = FakeEmailService(should_fail=True)
        result = await fake.send_email(...)
        assert result is False
    """

    def __init__(self, should_fail: bool = False) -> None:
        self.sent: list[CapturedEmail] = []
        self.should_fail = should_fail

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str = "",
    ) -> bool:
        if self.should_fail:
            return False
        self.sent.append(
            CapturedEmail(to=to, subject=subject, html_body=html_body, text_body=text_body)
        )
        return True

    def clear(self) -> None:
        """Clear all captured emails."""
        self.sent.clear()
