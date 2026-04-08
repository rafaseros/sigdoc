"""Email infrastructure — adapters and factory.

Spec: REQ-EMAIL-06
Design: ADR-ASEW-04
"""

from app.config import get_settings
from app.domain.ports.email_service import EmailService


def get_email_service() -> EmailService:
    """Factory: return the configured email adapter.

    Reads Settings.email_backend:
    - "console" (default) → ConsoleEmailService (logs to stdout, safe for dev)
    - "smtp" → SmtpEmailService (sends real emails via aiosmtplib)

    Usable as a FastAPI dependency:
        service: EmailService = Depends(get_email_service)
    """
    settings = get_settings()
    backend = settings.email_backend.lower()

    if backend == "smtp":
        from .smtp_adapter import SmtpEmailService

        return SmtpEmailService(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            from_address=settings.smtp_from_address,
            use_tls=settings.smtp_tls,
        )

    # Default to console for any unrecognized backend (including "console")
    from .console_adapter import ConsoleEmailService

    return ConsoleEmailService()


__all__ = ["get_email_service"]
