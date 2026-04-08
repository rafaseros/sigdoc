"""EmailService — domain port for sending emails.

Spec: REQ-EMAIL-01
Design: ADR-ASEW-01
"""

from abc import ABC, abstractmethod


class EmailService(ABC):
    """Abstract port for sending transactional emails.

    Implementations must never raise — return False on failure.
    """

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str = "",
    ) -> bool:
        """Send an email.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            html_body: HTML body of the email.
            text_body: Plain-text fallback (optional).

        Returns:
            True on success, False on failure (never raises).
        """
        ...
