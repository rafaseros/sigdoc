import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import TenantMixin
from .base import Base, TimestampMixin, UUIDMixin


class TemplatePresetModel(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "template_presets"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "name", name="uq_template_presets_template_name"
        ),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
