import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, UUIDMixin


class TemplateShareModel(UUIDMixin, TenantMixin, Base):
    __tablename__ = "template_shares"
    __table_args__ = (
        UniqueConstraint("template_id", "user_id", name="uq_template_shares_template_user"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    template = relationship("TemplateModel", lazy="selectin")
    user = relationship("UserModel", foreign_keys=[user_id], lazy="selectin")
    sharer = relationship("UserModel", foreign_keys=[shared_by], lazy="selectin")
