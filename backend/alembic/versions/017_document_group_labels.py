"""Document group role/position — related_label + group_position

Revision ID: 017
Revises: 016
Create Date: 2026-08-14

Feature #4 (grouped generated documents). Migration 016 added
`documents.group_id` so that documents rendered together from one multi-file
generation share a group. This migration records each document's ROLE and
ORDER within its group so the group can be reconstructed without decoding the
filename:

  1. `documents.related_label` (nullable TEXT): NULL = the primary document;
     the related file's label (e.g. "Recibo de pago") for related documents.
  2. `documents.group_position` (INTEGER NOT NULL, server_default 0): 0 = the
     primary, 1..N = related files in render (position) order.

Both are additive and safe on existing rows: pre-migration documents get
related_label = NULL and group_position = 0 (the server_default), i.e. every
existing row is treated as a primary — which is exactly the correct default
for the pre-group single-file world.

downgrade() drops both columns. This is lossy for the recorded role/order
(the render order is still recoverable from created_at), which is expected and
acceptable for a downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("related_label", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "group_position",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("documents", "group_position")
    op.drop_column("documents", "related_label")
