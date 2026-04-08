from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.services import get_audit_service
from app.application.services.audit_service import AuditService
from app.presentation.middleware.tenant import CurrentUser, get_current_user
from app.presentation.schemas.audit import AuditActionEnum, AuditLogListResponse, AuditLogResponse

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_log(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    action: AuditActionEnum | None = Query(None),
    actor_id: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Return a paginated, filterable audit log for the current tenant.

    Admin-only — returns 403 for non-admin callers.
    Ordered by ``created_at DESC``.

    Query params:
    - page / size: pagination (size capped at 100)
    - action: filter by AuditAction constant (e.g. ``document.generate``)
    - actor_id: filter by the user who performed the action
    - date_from / date_to: ISO-8601 datetime boundaries (inclusive)
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden realizar esta acción",
        )

    entries, total = await audit_service.list_audit_logs(
        page=page,
        size=size,
        action=action.value if action is not None else None,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )

    items = [
        AuditLogResponse(
            id=str(entry.id),
            actor_id=str(entry.actor_id) if entry.actor_id is not None else None,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=str(entry.resource_id) if entry.resource_id is not None else None,
            details=entry.details,
            ip_address=entry.ip_address,
            created_at=entry.created_at,
        )
        for entry in entries
    ]

    return AuditLogListResponse(items=items, total=total, page=page, size=size)
