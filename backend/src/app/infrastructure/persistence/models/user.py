from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import TenantMixin
from .base import Base, TimestampMixin, UUIDMixin


class UserModel(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="document_generator", server_default="document_generator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    bulk_generation_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Email verification (added in migration 009)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Password reset (added in migration 009)
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_reset_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant = relationship("TenantModel", lazy="selectin")
