from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class AuditAction:
    """String constants for all audit action types."""

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
    AUTH_SIGNUP = "auth.signup"
    AUTH_RESET_PASSWORD = "auth.reset_password"


@dataclass
class AuditLog:
    id: UUID
    tenant_id: UUID
    action: str
    actor_id: UUID | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime | None = None
