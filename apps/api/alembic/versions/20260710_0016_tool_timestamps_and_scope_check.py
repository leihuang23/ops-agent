"""add tools timestamps and permission_scope CHECK constraint

Revision ID: 20260710_0016
Revises: 20260710_0015
Create Date: 2026-07-10 00:00:00.000000

Phase 6 schema alignment (PRD §9.1):

1. Add ``created_at`` / ``updated_at`` to the ``tools`` table. The PRD lists
   timestamps on the tools table but migration 0015 omitted them. Existing rows
   are backfilled with ``CURRENT_TIMESTAMP``; the application layer always sets
   explicit values thereafter (matching the ``agents`` table pattern).
2. Add a CHECK constraint ``ck_tools_permission_scope`` so the four-value enum
   (``read_data``, ``write_mock_action``, ``request_approval``, ``run_eval``)
   is enforced at the DB level, not only by the Pydantic ``PermissionScope``
   Literal. This prevents a raw DB insert outside the validated API from landing
   an invalid scope.

Strictly additive and reversible; portable across SQLite and PostgreSQL via
``batch_alter_table``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260710_0016"
down_revision: str | None = "20260710_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tools") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.create_check_constraint(
            "ck_tools_permission_scope",
            "permission_scope IN ('read_data', 'write_mock_action', "
            "'request_approval', 'run_eval')",
        )


def downgrade() -> None:
    with op.batch_alter_table("tools") as batch_op:
        batch_op.drop_constraint(
            "ck_tools_permission_scope", type_="check"
        )
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
