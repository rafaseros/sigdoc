from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.jwt_handler import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.infrastructure.persistence.database import get_session
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.middleware.tenant import get_current_user, CurrentUser
from app.presentation.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Authenticate user and return JWT tokens."""
    repo = SQLAlchemyUserRepository(session)
    user = await repo.get_by_email(request.email)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
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
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(request.refresh_token)
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
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
    )
