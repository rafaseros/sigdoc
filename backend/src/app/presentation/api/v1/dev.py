"""Dev-only recovery endpoint for the canonical admin account.

WARNING: This endpoint is EXCLUSIVELY for local development use.
- It MUST never be enabled in production. It is pinned OFF in
  docker-compose.prod.yml (ENABLE_DEV_RESET: "false"), which overrides any
  ENABLE_DEV_RESET value that might drift into the droplet .env.
- It is only registered in the FastAPI app when settings.enable_dev_reset is True.
- It requires a shared secret token: callers MUST send the value of
  settings.dev_reset_token in the X-Dev-Reset-Token request header. The endpoint
  FAILS CLOSED (HTTP 403) when the token is unset/empty or the header is
  missing/mismatched — "enabled but no token configured" is NOT an open door.
- It resets the canonical admin to a RANDOMLY generated password, returned ONCE
  in the JSON response so the operator can log in. There is no publicly-known
  password anymore.
- When triggered, it leaves an alarming audit trail: AuditAction.DEV_ADMIN_RESET.
  Any production audit log search for "dev.admin_reset" is an immediate red flag.

Local-dev usage: set ENABLE_DEV_RESET=true and DEV_RESET_TOKEN=<secret> in .env,
restart the api container, then see scripts/dev-reset-admin.sh for the curl helper.

Production admin recovery does NOT use this HTTP endpoint. It is a server-side
operation gated by host access — see scripts/reset-admin.sh (docker exec).
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service
from app.config import get_settings
from app.domain.entities.audit_log import AuditAction
from app.infrastructure.auth.jwt_handler import hash_password
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.middleware.tenant import get_tenant_session

router = APIRouter()

_CANONICAL_EMAIL = "devrafaseros@gmail.com"
# Length (in bytes of entropy) of the randomly generated recovery password.
# token_urlsafe(32) yields a ~43-char URL-safe string — strong and copy-pasteable.
_GENERATED_PASSWORD_BYTES = 32


@router.post("/reset-admin")
async def reset_canonical_admin(
    x_dev_reset_token: str | None = Header(default=None, alias="X-Dev-Reset-Token"),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Reset the canonical admin account to a known-good state.

    LOCAL-DEV-ONLY ENDPOINT — must never be enabled in production (pinned off).

    Auth: requires the X-Dev-Reset-Token header to match settings.dev_reset_token
    (constant-time compare). FAILS CLOSED with HTTP 403 when the token is
    unset/empty or the header is missing/wrong — without revealing which.

    Target: devrafaseros@gmail.com. Sets a freshly generated random password
    (returned ONCE in the response), role=admin, is_active=True,
    email_verified=True. Clears password_reset_token, password_reset_sent_at,
    email_verification_token, email_verification_sent_at.

    If the canonical admin user does not exist in the DB → 404.
    The migration 008 is responsible for seeding the canonical admin.

    On success: emits an alarming DEV_ADMIN_RESET audit log entry.
    Any such entry in a production audit log is an immediate security incident.
    """
    settings = get_settings()
    configured_token = settings.dev_reset_token

    # Fail closed: no server-side secret configured OR missing/mismatched header.
    # A single generic 403 avoids revealing which precondition failed.
    if (
        not configured_token
        or x_dev_reset_token is None
        or not secrets.compare_digest(x_dev_reset_token, configured_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden.",
        )

    repo = SQLAlchemyUserRepository(session)

    user = await repo.get_by_email(_CANONICAL_EMAIL)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Canonical admin {_CANONICAL_EMAIL!r} not found. Run migration 008 first.",
        )

    # Generate a strong random password per call — no publicly-known password.
    # It is returned ONCE in the response and never logged or persisted in clear.
    new_password = secrets.token_urlsafe(_GENERATED_PASSWORD_BYTES)
    new_hashed = hash_password(new_password)
    await repo.update(
        user.id,
        hashed_password=new_hashed,
        role="admin",
        is_active=True,
        email_verified=True,
        password_reset_token=None,
        password_reset_sent_at=None,
        email_verification_token=None,
        email_verification_sent_at=None,
    )

    # Alarming audit trail — presence of this action in production is a security incident.
    # The generated password is deliberately NOT included in the audit details.
    audit_svc = get_audit_service()
    audit_svc.log(
        actor_id=user.id,  # self-reset semantics — no authenticated actor
        tenant_id=user.tenant_id,
        action=AuditAction.DEV_ADMIN_RESET,
        resource_type="user",
        resource_id=user.id,
        details={
            "target_email": _CANONICAL_EMAIL,
            "via": "dev_endpoint",
        },
    )

    return {
        "message": "Canonical admin reset",
        "email": _CANONICAL_EMAIL,
        "password": new_password,
    }
