import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class TenantModel(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    tier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscription_tiers.id"),
        nullable=True,
        index=True,
    )

    tier = relationship("SubscriptionTierModel", lazy="selectin")
