import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, UUIDMixin


class DocumentModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_tenant_created", "tenant_id", "created_at", postgresql_using="btree"),
        Index("ix_documents_tenant_template_version", "tenant_id", "template_version_id"),
        Index(
            "ix_documents_batch",
            "batch_id",
            postgresql_where="batch_id IS NOT NULL",
        ),
    )

    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id"),
        nullable=False,
    )
    minio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    generation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    variables_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", server_default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    template_version = relationship("TemplateVersionModel", lazy="selectin")
    creator = relationship("UserModel", lazy="selectin")
