import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import TenantMixin
from .base import Base, UUIDMixin


class UsageEventModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_usage_events_user_created", "user_id", "created_at"),
        Index("ix_usage_events_template", "template_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id"),
        nullable=True,
    )
    generation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    document_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
