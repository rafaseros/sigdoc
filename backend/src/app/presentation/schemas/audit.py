from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class AuditActionEnum(str, Enum):
    """FastAPI-compatible enum for filtering audit log by action."""

    TEMPLATE_UPLOAD = "template.upload"
    TEMPLATE_DELETE = "template.delete"
    TEMPLATE_VERSION = "template.version"
    TEMPLATE_SHARE = "template.share"
    TEMPLATE_UNSHARE = "template.unshare"

    DOCUMENT_GENERATE = "document.generate"
    DOCUMENT_GENERATE_BULK = "document.generate_bulk"
    DOCUMENT_DELETE = "document.delete"

    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DEACTIVATE = "user.deactivate"

    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_CHANGE_PASSWORD = "auth.change_password"


class AuditLogResponse(BaseModel):
    """Single audit log entry returned to API consumers."""

    id: str
    actor_id: str | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    items: list[AuditLogResponse]
    total: int
    page: int
    size: int
