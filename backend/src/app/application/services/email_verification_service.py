"""EmailVerificationService — handles email verification token lifecycle.

Spec: REQ-VERIFY-02, REQ-VERIFY-03, REQ-VERIFY-04
Design: ADR-ASEW-02 (tokens in users table), ADR-ASEW-03 (fire-and-forget)
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.ports.email_service import EmailService
from app.domain.ports.user_repository import UserRepository

# Verification token expires in 24 hours
_VERIFICATION_EXPIRY_HOURS = 24

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "infrastructure" / "email" / "templates"


def _render_verification_email(
    user_name: str,
    action_url: str,
    app_name: str = "SigDoc",
) -> tuple[str, str]:
    """Render the verification email templates. Returns (html, text) tuple."""
    try:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
        template = env.get_template("verification.html")
        html = template.render(
            app_name=app_name,
            user_name=user_name,
            action_url=action_url,
            expires_in=f"{_VERIFICATION_EXPIRY_HOURS} horas",
        )
    except Exception:
        html = (
            f"<p>Hola {user_name},</p>"
            f"<p>Verificá tu correo: <a href='{action_url}'>{action_url}</a></p>"
        )

    text = (
        f"Hola {user_name},\n\n"
        f"Verificá tu correo haciendo clic en el siguiente enlace:\n{action_url}\n\n"
        f"Este enlace expira en {_VERIFICATION_EXPIRY_HOURS} horas."
    )
    return html, text


class EmailVerificationService:
    """Manages email verification token generation, sending, and validation."""

    @staticmethod
    async def send_verification(
        user,
        email_service: EmailService,
        user_repo: UserRepository,
        frontend_url: str = "http://localhost:5173",
        app_name: str = "SigDoc",
    ) -> None:
        """Generate a verification token, store it, and send the email.

        This is fire-and-forget — failures are logged but do not raise.
        The user account is already created at this point.
        """
        token = secrets.token_hex(32)  # 64-char hex
        sent_at = datetime.now(timezone.utc)

        # Persist token to user record
        await user_repo.update(
            user.id,
            email_verification_token=token,
            email_verification_sent_at=sent_at,
        )

        action_url = f"{frontend_url}/verify-email?token={token}"
        html, text = _render_verification_email(
            user_name=user.full_name,
            action_url=action_url,
            app_name=app_name,
        )

        # Fire-and-forget — don't block signup on email delivery
        asyncio.create_task(
            email_service.send_email(
                to=user.email,
                subject=f"Verificá tu correo — {app_name}",
                html_body=html,
                text_body=text,
            )
        )

    @staticmethod
    async def verify_token(
        token: str,
        user_repo: UserRepository,
    ) -> tuple[bool, str]:
        """Verify the given token and mark the user's email as verified.

        Returns:
            (True, "") on success.
            (False, reason) on failure — reason is a Spanish user-facing message.
        """
        user = await user_repo.get_by_verification_token(token)

        if user is None:
            return False, "El enlace de verificación no es válido"

        # Check if already verified
        email_verified = getattr(user, "email_verified", False)
        if email_verified:
            return True, ""  # Idempotent — already verified is fine

        # Check expiry
        sent_at = getattr(user, "email_verification_sent_at", None)
        if sent_at is not None:
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            expiry = sent_at + timedelta(hours=_VERIFICATION_EXPIRY_HOURS)
            if datetime.now(timezone.utc) > expiry:
                return False, "El enlace de verificación ha expirado"

        # Mark as verified and clear the token
        await user_repo.update(
            user.id,
            email_verified=True,
            email_verification_token=None,
            email_verification_sent_at=None,
        )

        return True, ""

    @staticmethod
    async def resend_verification(
        user,
        email_service: EmailService,
        user_repo: UserRepository,
        frontend_url: str = "http://localhost:5173",
        app_name: str = "SigDoc",
    ) -> tuple[bool, str]:
        """Resend verification email to the user.

        Returns:
            (True, "") on success.
            (False, reason) if user is already verified.
        """
        email_verified = getattr(user, "email_verified", False)
        if email_verified:
            return False, "El correo ya está verificado"

        # Generate fresh token
        await EmailVerificationService.send_verification(
            user=user,
            email_service=email_service,
            user_repo=user_repo,
            frontend_url=frontend_url,
            app_name=app_name,
        )

        return True, ""
