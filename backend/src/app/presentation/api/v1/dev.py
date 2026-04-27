"""Dev-only recovery endpoint for the canonical admin account.

WARNING: This endpoint is EXCLUSIVELY for development use.
- It MUST never be enabled in production (ENABLE_DEV_RESET=true in .env).
- It is only registered in the FastAPI app when settings.enable_dev_reset is True.
- When triggered, it leaves an alarming audit trail: AuditAction.DEV_ADMIN_RESET.
  Any production audit log search for "dev.admin_reset" is an immediate red flag.
- The target email and password are HARDCODED — this endpoint is NOT parameterizable.
  It exists solely to recover the canonical admin account when the admin is locked out.

Activation: set ENABLE_DEV_RESET=true in .env and restart the api container.
See scripts/dev-reset-admin.sh for the curl helper.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service
from app.domain.entities.audit_log import AuditAction
from app.infrastructure.auth.jwt_handler import hash_password
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.middleware.tenant import get_tenant_session

router = APIRouter()

_CANONICAL_EMAIL = "devrafaseros@gmail.com"
_CANONICAL_PASSWORD = "admin123!"


@router.post("/reset-admin")
async def reset_canonical_admin(
    session: AsyncSession = Depends(get_tenant_session),
):
    """Reset the canonical admin account to a known state.

    DEV-ONLY ENDPOINT — must never be enabled in production.

    Hardcoded target: devrafaseros@gmail.com → password: admin123!
    Sets role=admin, is_active=True, email_verified=True.
    Clears password_reset_token, password_reset_sent_at,
    email_verification_token, email_verification_sent_at.

    If the canonical admin user does not exist in the DB → 404.
    The migration 008 is responsible for seeding the canonical admin.

    On success: emits an alarming DEV_ADMIN_RESET audit log entry.
    Any such entry in a production audit log is an immediate security incident.
    """
    repo = SQLAlchemyUserRepository(session)

    user = await repo.get_by_email(_CANONICAL_EMAIL)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Canonical admin {_CANONICAL_EMAIL!r} not found. Run migration 008 first.",
        )

    new_hashed = hash_password(_CANONICAL_PASSWORD)
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

    # Alarming audit trail — presence of this action in production is a security incident
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

    return {"message": "Canonical admin reset", "email": _CANONICAL_EMAIL}
