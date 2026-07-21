import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, UUIDMixin


class TemplateVersionFileModel(UUIDMixin, TenantMixin, Base):
    """A related .docx attached to a template version (besides the primary).

    Labels are unique per version; `position` drives the rendering order of
    the related files after the primary. Rows cascade-delete with their
    parent version.
    """

    __tablename__ = "template_version_files"
    __table_args__ = (
        UniqueConstraint(
            "version_id", "label", name="uq_template_version_files_version_label"
        ),
        Index("ix_template_version_files_tenant_version", "tenant_id", "version_id"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    minio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    file_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    version = relationship("TemplateVersionModel", back_populates="files")
