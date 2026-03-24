import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, TimestampMixin, UUIDMixin


class TemplateModel(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_templates_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    versions = relationship("TemplateVersionModel", back_populates="template", lazy="selectin")
    creator = relationship("UserModel", lazy="selectin")
