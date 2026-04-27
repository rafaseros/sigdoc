"""Role expansion — introduce template_creator and document_generator roles

Revision ID: 011
Revises: 010
Create Date: 2026-04-25

Spec: REQ-ROLE-02, REQ-ROLE-03
Design: ADR-ROLE-02

Transforms the two-role model (admin / user) into a three-role model:
  - admin            — unchanged
  - template_creator — can upload/manage templates (was "user")
  - document_generator — can only generate documents (new default for new users)

upgrade() — critical order per ADR-ROLE-02:
  1. UPDATE rows FIRST while they still hold the old "user" value.
     This ensures all pre-existing non-admin users become "template_creator"
     (preserving their current capabilities during the transition).
  2. THEN alter the column default to "document_generator".
     New users created after this migration receive the least-privilege role.

downgrade() — LOSSY: both template_creator and document_generator collapse back
  to "user". There is no way to distinguish which rows were originally
  "document_generator" (newly created after upgrade) vs "template_creator"
  (promoted from "user"). Downgrade is provided for emergency rollback only.
  WARNING: any users created after the upgrade (as document_generator) will
  become "user" on downgrade, which has the same capabilities as template_creator
  in the legacy model — a capability expansion, not a reduction. Plan accordingly.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "011"
down_revision: str = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. UPDATE first — while existing rows still hold 'user', transform them.
    #    Admins are unaffected (WHERE role = 'user' skips them).
    #    Idempotent: if re-run, WHERE matches nothing.
    op.execute("UPDATE users SET role = 'template_creator' WHERE role = 'user'")

    # 2. THEN change the column default for future INSERT statements.
    #    New users will be document_generator (least privilege) by default.
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(20),
        server_default="document_generator",
    )


def downgrade() -> None:
    # LOSSY downgrade — see module docstring for caveats.

    # 1. Revert default first, before touching rows.
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(20),
        server_default="user",
    )

    # 2. THEN collapse both new roles back to 'user'.
    op.execute(
        "UPDATE users SET role = 'user' "
        "WHERE role IN ('template_creator', 'document_generator')"
    )
