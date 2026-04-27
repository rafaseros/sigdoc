from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service, get_quota_service
from app.application.services.quota_service import QuotaService
from app.domain.entities import AuditAction
from app.domain.services.permissions import is_admin_role
from app.infrastructure.auth.jwt_handler import hash_password
from app.infrastructure.persistence.models.tenant import TenantModel
from app.infrastructure.persistence.models.user import UserModel
from app.infrastructure.persistence.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.api.dependencies import require_user_manager
from app.presentation.middleware.tenant import CurrentUser, get_tenant_session
from app.presentation.schemas.user import (
    CreateUserRequest,
    ResetPasswordByAdminRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)

router = APIRouter()

# Backwards-compat alias — kept so external callers / tests importing
# `require_admin` from this module continue to work. Prefer
# `app.presentation.api.dependencies.require_user_manager` for new code.
require_admin = require_user_manager


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
    quota_service: QuotaService = Depends(get_quota_service),
):
    """Create a new user in the admin's tenant."""
    repo = SQLAlchemyUserRepository(session)

    # Quota check — enforce max_users limit for the tenant's tier
    tenant_stmt = select(TenantModel).where(TenantModel.id == admin.tenant_id)
    tenant_result = await session.execute(tenant_stmt)
    tenant = tenant_result.scalar_one_or_none()
    if tenant is not None and tenant.tier_id is not None:
        await quota_service.check_user_limit(
            tenant_id=admin.tenant_id,
            tier_id=tenant.tier_id,
        )

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
        role="document_generator",
    )
    created = await repo.create(user)

    # Fire-and-forget audit
    audit_svc = get_audit_service()
    audit_svc.log(
        actor_id=admin.user_id,
        tenant_id=admin.tenant_id,
        action=AuditAction.USER_CREATE,
        resource_type="user",
        resource_id=created.id,
        details={"email": created.email},
    )

    return UserResponse(
        id=str(created.id),
        email=created.email,
        full_name=created.full_name,
        role=created.role,
        is_active=created.is_active,
        created_at=created.created_at,
        bulk_generation_limit=getattr(created, "bulk_generation_limit", None),
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
            bulk_generation_limit=getattr(u, "bulk_generation_limit", None),
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

    # Last-admin guard: if demoting from admin, ensure at least one admin remains
    if "role" in update_data and not is_admin_role(update_data["role"]):
        target_user = await repo.get_by_id(user_id)
        if target_user and is_admin_role(target_user.role):
            admin_count = await repo.count_admins_by_tenant(admin.tenant_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede degradar al último administrador del tenant",
                )

    user = await repo.update(user_id, **update_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    # Fire-and-forget audit
    audit_svc = get_audit_service()
    audit_svc.log(
        actor_id=admin.user_id,
        tenant_id=admin.tenant_id,
        action=AuditAction.USER_UPDATE,
        resource_type="user",
        resource_id=user_id,
        details={k: str(v) for k, v in update_data.items() if k != "hashed_password"},
    )

    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        bulk_generation_limit=getattr(user, "bulk_generation_limit", None),
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

    # Last-admin guard: cannot deactivate the last admin in a tenant
    if is_admin_role(user.role):
        admin_count = await repo.count_admins_by_tenant(admin.tenant_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede desactivar al último administrador del tenant",
            )

    await repo.deactivate(user_id)

    # Fire-and-forget audit
    audit_svc = get_audit_service()
    audit_svc.log(
        actor_id=admin.user_id,
        tenant_id=admin.tenant_id,
        action=AuditAction.USER_DEACTIVATE,
        resource_type="user",
        resource_id=user_id,
    )


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: UUID,
    request: ResetPasswordByAdminRequest,
    admin: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Reset a user's password (admin only).

    Hashes the new password, clears any stale password-reset tokens, and
    emits an audit log event with USER_PASSWORD_RESET_BY_ADMIN action.
    """
    repo = SQLAlchemyUserRepository(session)

    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    new_hashed = hash_password(request.new_password)
    await repo.update(
        user_id,
        hashed_password=new_hashed,
        password_reset_token=None,
        password_reset_sent_at=None,
    )

    # Fire-and-forget audit
    audit_svc = get_audit_service()
    audit_svc.log(
        actor_id=admin.user_id,
        tenant_id=admin.tenant_id,
        action=AuditAction.USER_PASSWORD_RESET_BY_ADMIN,
        resource_type="user",
        resource_id=user_id,
        details={
            "actor_id": str(admin.user_id),
            "target_user_id": str(user_id),
        },
    )

    return {"message": "Password reset successfully"}
