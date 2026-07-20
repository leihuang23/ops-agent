"""backfill the immutable v1 snapshot's governed action tool IDs

Revision ID: 20260719_0018
Revises: 20260719_0017
Create Date: 2026-07-19 00:00:00.000000

The seeded ``ledger_v1`` snapshot predates the governed action tools: its
``allowed_scopes`` have always authorized ``write_mock_action`` and
``request_approval`` (migration 20260709_0012), but its ``enabled_tool_ids``
never received the matching tool IDs. Until now a hard-coded exception in the
agent service let exactly this snapshot propose report actions by scope alone,
bypassing the uniform ``can_call_tool`` tool-and-scope check every other
version is subject to.

This data migration closes the asymmetry at the data layer: the published
``ledger_v1`` row gains ``create_mock_action`` and ``request_approval`` in
``enabled_tool_ids``, so the standard policy check governs it with no special
cases. Fresh seeds write the same list directly. Historical runs are
unaffected: their steps are already materialized, and the backfill only
changes how future runs dispatch.

The downgrade removes exactly the two tool IDs this migration adds.
"""

from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "20260719_0018"
down_revision: str | None = "20260719_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

V1_VERSION_ID = "ledger_v1"
V1_AGENT_ID = "ledger"
ACTION_TOOL_IDS: tuple[str, ...] = ("create_mock_action", "request_approval")


def _agent_versions_table() -> sa.Table:
    return sa.table(
        "agent_versions",
        sa.column("id", sa.String(128)),
        sa.column("agent_id", sa.String(64)),
        sa.column("status", sa.String(32)),
        sa.column("enabled_tool_ids", sa.JSON),
        sa.column("updated_at", sa.DateTime),
    )


def _v1_row(
    conn: sa.engine.Connection, agent_versions: sa.Table
) -> sa.engine.Row | None:
    return conn.execute(
        sa.select(agent_versions.c.id, agent_versions.c.enabled_tool_ids).where(
            agent_versions.c.id == V1_VERSION_ID,
            agent_versions.c.agent_id == V1_AGENT_ID,
            agent_versions.c.status == "published",
        )
    ).one_or_none()


def upgrade() -> None:
    conn = op.get_bind()
    agent_versions = _agent_versions_table()
    row = _v1_row(conn, agent_versions)
    if row is None:
        return
    current = list(row[1] or [])
    missing = [tool_id for tool_id in ACTION_TOOL_IDS if tool_id not in current]
    if not missing:
        return
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        sa.update(agent_versions)
        .where(agent_versions.c.id == V1_VERSION_ID)
        .values(enabled_tool_ids=[*current, *missing], updated_at=now)
    )


def downgrade() -> None:
    conn = op.get_bind()
    agent_versions = _agent_versions_table()
    row = _v1_row(conn, agent_versions)
    if row is None:
        return
    current = list(row[1] or [])
    reverted = [tool_id for tool_id in current if tool_id not in ACTION_TOOL_IDS]
    if reverted == current:
        return
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn.execute(
        sa.update(agent_versions)
        .where(agent_versions.c.id == V1_VERSION_ID)
        .values(enabled_tool_ids=reverted, updated_at=now)
    )
