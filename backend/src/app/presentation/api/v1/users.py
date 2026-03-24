from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.auth.jwt_handler import hash_password
from app.infrastructure.persistence.models.user import UserModel
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.middleware.tenant import CurrentUser, get_current_user, get_tenant_session
from app.presentation.schemas.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)

router = APIRouter()


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden realizar esta acción",
        )
    return current_user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a new user in the admin's tenant."""
    repo = SQLAlchemyUserRepository(session)

    # Check email uniqueness within tenant
    existing = await repo.get_by_email(request.email.lower())
    if existing and existing.tenant_id == admin.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese correo electrónico en este tenant",
        )

    user = UserModel(
        email=request.email.lower(),
        full_name=request.full_name,
        hashed_password=hash_password(request.password),
        tenant_id=admin.tenant_id,
        role="user",
    )
    created = await repo.create(user)

    return UserResponse(
        id=str(created.id),
        email=created.email,
        full_name=created.full_name,
        role=created.role,
        is_active=created.is_active,
        created_at=created.created_at,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
):
    """List all users in the admin's tenant."""
    repo = SQLAlchemyUserRepository(session)
    users, total = await repo.list_by_tenant(page=page, size=size)

    items = [
        UserResponse(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]

    return UserListResponse(items=items, total=total, page=page, size=size)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Update a user's fields (admin only)."""
    repo = SQLAlchemyUserRepository(session)

    # Build update kwargs from non-None fields
    update_data = request.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se proporcionaron campos para actualizar",
        )

    # If email is being changed, check uniqueness
    if "email" in update_data:
        existing = await repo.get_by_email(update_data["email"])
        if existing and existing.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese correo electrónico en este tenant",
            )

    user = await repo.update(user_id, **update_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: UUID,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Soft delete a user (set is_active=False)."""
    repo = SQLAlchemyUserRepository(session)

    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    await repo.deactivate(user_id)
