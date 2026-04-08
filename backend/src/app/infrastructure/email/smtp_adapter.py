"""SmtpEmailService — production adapter using aiosmtplib.

Spec: REQ-EMAIL-02
Design: ADR-ASEW-03 (fire-and-forget, never raises)
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.domain.ports.email_service import EmailService

logger = logging.getLogger(__name__)


class SmtpEmailService(EmailService):
    """Sends emails via SMTP using aiosmtplib.

    Returns False on any failure instead of raising — the caller is responsible
    for deciding whether to retry (but typically this is fire-and-forget).
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls

    async def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str = "",
    ) -> bool:
        try:
            import aiosmtplib

            message = MIMEMultipart("alternative")
            message["From"] = self._from_address
            message["To"] = to
            message["Subject"] = subject

            if text_body:
                message.attach(MIMEText(text_body, "plain", "utf-8"))
            message.attach(MIMEText(html_body, "html", "utf-8"))

            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username or None,
                password=self._password or None,
                use_tls=self._use_tls,
            )
            return True

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "SmtpEmailService failed to send email to %s: %s",
                to,
                exc,
                exc_info=True,
            )
            return False
