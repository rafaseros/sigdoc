"""ConsoleEmailService — development adapter that logs emails to stdout.

Spec: REQ-EMAIL-03
Design: ADR-ASEW-04
"""

import logging
from dataclasses import dataclass, field

from app.domain.ports.email_service import EmailService

logger = logging.getLogger(__name__)


@dataclass
class SentEmail:
    """Record of an email sent via the console adapter."""
    to: str
    subject: str
    html_body: str
    text_body: str


class ConsoleEmailService(EmailService):
    """Logs emails to stdout instead of sending them.

    Stores all sent emails in self.sent_emails for test inspection.
    Always returns True — the console never fails.
    """

    def __init__(self) -> None:
        self.sent_emails: list[SentEmail] = []

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str = "",
    ) -> bool:
        email = SentEmail(to=to, subject=subject, html_body=html_body, text_body=text_body)
        self.sent_emails.append(email)

        logger.info(
            "=== [ConsoleEmailService] ===\n"
            "To:      %s\n"
            "Subject: %s\n"
            "Body:\n%s\n"
            "============================",
            to,
            subject,
            text_body or html_body,
        )
        return True
