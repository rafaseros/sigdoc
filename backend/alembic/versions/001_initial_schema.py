"""Initial schema - tenants, users, templates, template_versions, documents

Revision ID: 001
Revises:
Create Date: 2026-03-23

"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # --- templates ---
    op.create_table(
        "templates",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_templates_tenant_name"),
    )

    # --- template_versions ---
    op.create_table(
        "template_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "template_id",
            sa.Uuid(),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("minio_path", sa.String(500), nullable=False),
        sa.Column("variables", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("template_id", "version", name="uq_template_versions_template_version"),
        sa.Index("ix_template_versions_tenant_template", "tenant_id", "template_id"),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "template_version_id",
            sa.Uuid(),
            sa.ForeignKey("template_versions.id"),
            nullable=False,
        ),
        sa.Column("minio_path", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("generation_type", sa.String(10), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=True),
        sa.Column("variables_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="completed", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index("ix_documents_tenant_created", "tenant_id", "created_at"),
        sa.Index("ix_documents_tenant_template_version", "tenant_id", "template_version_id"),
    )

    # Partial index on batch_id (only non-null values)
    op.create_index(
        "ix_documents_batch",
        "documents",
        ["batch_id"],
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )

    # --- Seed data: default tenant + admin user ---
    import uuid

    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@sigdoc.local")
    hashed = pwd_context.hash(admin_password)

    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    op.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, is_active) "
            "VALUES (CAST(:tid AS uuid), :name, :slug, true)"
        ).bindparams(tid=str(tenant_id), name="Default", slug="default")
    )

    op.execute(
        sa.text(
            "INSERT INTO users (id, tenant_id, email, hashed_password, full_name, role, is_active) "
            "VALUES (CAST(:uid AS uuid), CAST(:tid AS uuid), :email, :hashed_password, :full_name, :role, true)"
        ).bindparams(
            uid=str(admin_id),
            tid=str(tenant_id),
            email=admin_email,
            hashed_password=hashed,
            full_name="System Admin",
            role="admin",
        )
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("template_versions")
    op.drop_table("templates")
    op.drop_table("users")
    op.drop_table("tenants")
