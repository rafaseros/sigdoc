from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service
from app.application.services.signup_service import SignupService, SignupError
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
from app.infrastructure.persistence.repositories.tenant_repository import SQLAlchemyTenantRepository
from app.infrastructure.persistence.repositories.subscription_tier_repository import SQLAlchemySubscriptionTierRepository
from slowapi.util import get_remote_address

from app.presentation.middleware.rate_limit import limiter, tier_limit_refresh
from app.presentation.middleware.tenant import get_current_user, get_tenant_session, CurrentUser
from app.presentation.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
    SignupRequest,
    SignupResponse,
    SignupUserResponse,
)
from app.presentation.schemas.user import ChangePasswordRequest

router = APIRouter()


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().rate_limit_signup, key_func=get_remote_address)
async def signup(
    request: Request,
    body: SignupRequest,
    session: AsyncSession = Depends(get_session),
):
    """Self-service tenant signup — creates a new tenant + admin user atomically."""
    user_repo = SQLAlchemyUserRepository(session)
    tenant_repo = SQLAlchemyTenantRepository(session)
    tier_repo = SQLAlchemySubscriptionTierRepository(session)
    audit_svc = get_audit_service()
    ip = request.client.host if request.client else None

    service = SignupService(
        tenant_repo=tenant_repo,
        user_repo=user_repo,
        tier_repo=tier_repo,
        audit_service=audit_svc,
    )

    try:
        result = await service.signup(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            org_name=body.organization_name,
            ip_address=ip,
        )
    except SignupError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    return SignupResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        user=SignupUserResponse(
            id=str(result.user.id),
            email=result.user.email,
            full_name=result.user.full_name,
            role=result.user.role,
            tenant_id=str(result.user.tenant_id),
        ),
    )


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
async def refresh_token(request: Request, body: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return TokenResponse(
            access_token=create_access_token(
                user_id=payload["sub"],
                tenant_id=payload["tenant_id"],
                role=payload.get("role", "user"),
            ),
            refresh_token=create_refresh_token(
                user_id=payload["sub"],
                tenant_id=payload["tenant_id"],
            ),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
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
    settings = get_settings()
    effective_bulk_limit = (
        user.bulk_generation_limit
        if user.bulk_generation_limit is not None
        else settings.bulk_generation_limit
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
        effective_bulk_limit=effective_bulk_limit,
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
