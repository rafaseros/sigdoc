from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service
from app.config import get_settings
from app.domain.entities import AuditAction
from app.infrastructure.auth.jwt_handler import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from slowapi.util import get_remote_address

from app.presentation.middleware.rate_limit import limiter, tier_limit_refresh
from app.presentation.middleware.tenant import get_current_user, get_tenant_session, CurrentUser
from app.presentation.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
)
from app.presentation.schemas.user import ChangePasswordRequest

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().rate_limit_login, key_func=get_remote_address)
async def login(request: Request, body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Authenticate user and return JWT tokens."""
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_email(body.email)

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Fire-and-forget audit for successful login
    audit_svc = get_audit_service()
    ip = request.client.host if request.client else None
    audit_svc.log(
        actor_id=user.id,
        tenant_id=user.tenant_id,
        action=AuditAction.AUTH_LOGIN,
        resource_type="user",
        resource_id=user.id,
        ip_address=ip,
    )

    return TokenResponse(
        access_token=create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
        ),
        refresh_token=create_refresh_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(tier_limit_refresh)
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    """Refresh access token using refresh token.

    ADR-ROLE-01: role is re-fetched from DB (never from the token payload).
    REQ-ROLE-09: new access token carries the DB-current role.
    REQ-ROLE-10: returns 401 if user no longer exists or is inactive.
    """
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Re-fetch user from DB — single source of truth for role (ADR-ROLE-01)
    from uuid import UUID as _UUID
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_id(_UUID(payload["sub"]))

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            role=user.role,  # always from DB, never from token payload
        ),
        refresh_token=create_refresh_token(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current authenticated user info."""
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_id(current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    me_settings = get_settings()
    effective_bulk_limit = (
        user.bulk_generation_limit
        if user.bulk_generation_limit is not None
        else me_settings.bulk_generation_limit
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
        effective_bulk_limit=effective_bulk_limit,
        email_verified=getattr(user, "email_verified", True),
    )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Change the current user's password."""
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_id(current_user.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )

    await repo.update(current_user.user_id, hashed_password=hash_password(body.new_password))

    # Fire-and-forget audit
    audit_svc = get_audit_service()
    ip = request.client.host if request.client else None
    audit_svc.log(
        actor_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        action=AuditAction.AUTH_CHANGE_PASSWORD,
        resource_type="user",
        resource_id=current_user.user_id,
        ip_address=ip,
    )

    return {"message": "Contraseña actualizada correctamente"}
