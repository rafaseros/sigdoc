from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class SubscriptionTierModel(UUIDMixin, TimestampMixin, Base):
    """Global table — no TenantMixin; tiers are system-wide."""

    __tablename__ = "subscription_tiers"

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    monthly_document_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_templates: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bulk_generation_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default="10"
    )
    max_template_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Rate limit columns — slowapi format strings, e.g. "10/minute"
    rate_limit_login: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="5/minute"
    )
    rate_limit_refresh: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="10/minute"
    )
    rate_limit_generate: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="20/minute"
    )
    rate_limit_bulk: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="5/minute"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
