import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..database import TenantMixin
from .base import Base, TimestampMixin, UUIDMixin


class TemplateFolderModel(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "template_folders"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "owner_id", "name", name="uq_template_folders_tenant_owner_name"
        ),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
