from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import get_audit_service
from app.application.services.audit_service import AuditService
from app.infrastructure.persistence.models.user import UserModel
from app.presentation.api.dependencies import require_audit_viewer
from app.presentation.middleware.tenant import CurrentUser, get_tenant_session
from app.presentation.schemas.audit import AuditActionEnum, AuditLogListResponse, AuditLogResponse

router = APIRouter()


async def _load_actor_emails(
    session: AsyncSession,
    actor_ids: list[UUID],
) -> dict[UUID, str]:
    """Devuelve un mapeo de actor_id → email para los IDs indicados.

    Realiza una sola consulta en lote para todos los IDs únicos.
    """
    if not actor_ids:
        return {}
    stmt = select(UserModel.id, UserModel.email).where(UserModel.id.in_(actor_ids))
    result = await session.execute(stmt)
    return {row.id: row.email for row in result}


@router.get("", response_model=AuditLogListResponse)
async def list_audit_log(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    action: AuditActionEnum | None = Query(None),
    actor_id: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: CurrentUser = Depends(require_audit_viewer),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Retorna el registro de auditoría paginado y filtrable del tenant actual.

    Solo administradores — retorna 403 para otros roles.
    Ordenado por ``created_at DESC``.

    Parámetros de query:
    - page / size: paginación (size máximo 100)
    - action: filtra por tipo de acción (ej. ``document.generate``)
    - actor_id: filtra por el usuario que realizó la acción
    - date_from / date_to: límites de fecha en ISO-8601 (inclusive)
    """
    entries, total = await audit_service.list_audit_logs(
        page=page,
        size=size,
        action=action.value if action is not None else None,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )

    # Carga en lote los emails de todos los actores únicos de la página
    unique_actor_ids = list({e.actor_id for e in entries if e.actor_id is not None})
    email_by_id = await _load_actor_emails(session, unique_actor_ids)

    items = [
        AuditLogResponse(
            id=str(entry.id),
            actor_id=str(entry.actor_id) if entry.actor_id is not None else None,
            actor_email=email_by_id.get(entry.actor_id) if entry.actor_id is not None else None,
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
