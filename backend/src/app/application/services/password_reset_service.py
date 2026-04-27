"""DEPRECATED: route disabled per single-org-cutover; remove in Nivel B.

PasswordResetService — handles forgot password token lifecycle.

Spec: REQ-RESET-01, REQ-RESET-02, REQ-RESET-03
Design: ADR-ASEW-02 (tokens in users table), ADR-ASEW-03 (fire-and-forget)
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.entities.audit_log import AuditAction
from app.domain.ports.email_service import EmailService
from app.domain.ports.user_repository import UserRepository
from app.infrastructure.auth.jwt_handler import hash_password

# Reset token expires in 1 hour
_RESET_EXPIRY_HOURS = 1

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "infrastructure" / "email" / "templates"


def _render_reset_email(
    user_name: str,
    action_url: str,
    app_name: str = "SigDoc",
) -> tuple[str, str]:
    """Render the password reset email. Returns (html, text) tuple."""
    try:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
        template = env.get_template("password_reset.html")
        html = template.render(
            app_name=app_name,
            user_name=user_name,
            action_url=action_url,
            expires_in=f"{_RESET_EXPIRY_HOURS} hora",
        )
    except Exception:
        html = (
            f"<p>Hola {user_name},</p>"
            f"<p>Restablecé tu contraseña: <a href='{action_url}'>{action_url}</a></p>"
        )

    text = (
        f"Hola {user_name},\n\n"
        f"Restablecé tu contraseña haciendo clic en el siguiente enlace:\n{action_url}\n\n"
        f"Este enlace expira en {_RESET_EXPIRY_HOURS} hora."
    )
    return html, text


class PasswordResetService:
    """Manages password reset token generation, sending, and validation."""

    @staticmethod
    async def request_reset(
        email: str,
        email_service: EmailService,
        user_repo: UserRepository,
        frontend_url: str = "http://localhost:5173",
        app_name: str = "SigDoc",
    ) -> None:
        """Request a password reset for the given email.

        Always returns None (no indication of whether the user exists — anti-enumeration).
        If user exists, generates a token and sends the email fire-and-forget.
        """
        user = await user_repo.get_by_email(email)
        if user is None:
            # Anti-enumeration: do nothing but don't reveal non-existence
            return

        token = secrets.token_hex(32)  # 64-char hex
        sent_at = datetime.now(timezone.utc)

        # Store new token (overwrites any previous token)
        await user_repo.update(
            user.id,
            password_reset_token=token,
            password_reset_sent_at=sent_at,
        )

        action_url = f"{frontend_url}/reset-password?token={token}"
        html, text = _render_reset_email(
            user_name=user.full_name,
            action_url=action_url,
            app_name=app_name,
        )

        # Fire-and-forget
        asyncio.create_task(
            email_service.send_email(
                to=user.email,
                subject=f"Restablecé tu contraseña — {app_name}",
                html_body=html,
                text_body=text,
            )
        )

    @staticmethod
    async def reset_password(
        token: str,
        new_password: str,
        user_repo: UserRepository,
        audit_service=None,
    ) -> tuple[bool, str]:
        """Reset the user's password using the given token.

        Returns:
            (True, "") on success.
            (False, reason) on failure — reason is a Spanish user-facing message.
        """
        user = await user_repo.get_by_reset_token(token)

        if user is None:
            return False, "El enlace de restablecimiento no es válido"

        # Check expiry
        sent_at = getattr(user, "password_reset_sent_at", None)
        if sent_at is not None:
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            expiry = sent_at + timedelta(hours=_RESET_EXPIRY_HOURS)
            if datetime.now(timezone.utc) > expiry:
                return False, "El enlace de restablecimiento ha expirado"

        # Update password and clear the reset token (one-time use)
        hashed = hash_password(new_password)
        await user_repo.update(
            user.id,
            hashed_password=hashed,
            password_reset_token=None,
            password_reset_sent_at=None,
        )

        # Fire-and-forget audit log
        if audit_service is not None:
            audit_service.log(
                actor_id=user.id,
                tenant_id=user.tenant_id,
                action=AuditAction.AUTH_RESET_PASSWORD,
                resource_type="user",
                resource_id=user.id,
            )

        return True, ""
