"""wire agent_version to agent_runs

Revision ID: 20260708_0011
Revises: 20260708_0010
Create Date: 2026-07-08 12:00:00.000000

Adds agent_id and agent_version_id columns to agent_runs so every investigation
run records which published agent version executed it. Ensures the default
control-plane agent and v1 exist before applying NOT NULL / FK constraints so
that upgrades on existing databases succeed.
"""

from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_0011"
down_revision: str | None = "20260708_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_AGENT_ID = "revenue-ops-agent"
DEFAULT_VERSION_ID = "revenue-ops-agent_v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 1024
DEFAULT_SYSTEM_PROMPT = ""
DEFAULT_ENABLED_TOOLS = [
    "query_revenue_metrics",
    "fetch_account_details",
    "search_docs",
    "fetch_support_tickets",
]
DEFAULT_ALLOWED_SCOPES: list[str] = []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _insert_if_missing(
    conn: sa.engine.Connection,
    table: sa.TableClause,
    defaults: dict[str, object],
) -> None:
    """Insert a row if its primary key does not already exist.

    Portable across SQLite and PostgreSQL; safe because migrations run
    single-threaded during upgrade.
    """
    existing = conn.execute(
        sa.select(sa.literal(1)).where(table.c.id == defaults["id"])
    ).first()
    if existing is not None:
        return
    conn.execute(table.insert().values(**defaults))


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("agent_id", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("agent_version_id", sa.String(length=128), nullable=True)
        )

    op.create_index(
        "ix_agent_runs_agent_id",
        "agent_runs",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_runs_agent_version_id",
        "agent_runs",
        ["agent_version_id"],
    )

    conn = op.get_bind()

    agents = sa.table(
        "agents",
        sa.column("id", sa.String(64)),
        sa.column("name", sa.String(120)),
        sa.column("description", sa.Text),
        sa.column("default_model", sa.String(80)),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    agent_versions = sa.table(
        "agent_versions",
        sa.column("id", sa.String(128)),
        sa.column("agent_id", sa.String(64)),
        sa.column("version_number", sa.Integer),
        sa.column("semantic_version", sa.String(32)),
        sa.column("status", sa.String(32)),
        sa.column("system_prompt", sa.Text),
        sa.column("model", sa.String(80)),
        sa.column("temperature", sa.Float),
        sa.column("max_tokens", sa.Integer),
        sa.column("enabled_tool_ids", sa.JSON),
        sa.column("allowed_scopes", sa.JSON),
        sa.column("forked_from_version_id", sa.String(128)),
        sa.column("published_by", sa.String(80)),
        sa.column("published_at", sa.DateTime),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    now = _utcnow()
    _insert_if_missing(
        conn,
        agents,
        {
            "id": DEFAULT_AGENT_ID,
            "name": "Revenue Ops Agent",
            "description": "Control-plane revenue and support operations agent.",
            "default_model": DEFAULT_MODEL,
            "created_at": now,
            "updated_at": now,
        },
    )
    _insert_if_missing(
        conn,
        agent_versions,
        {
            "id": DEFAULT_VERSION_ID,
            "agent_id": DEFAULT_AGENT_ID,
            "version_number": 1,
            "semantic_version": "1.0.0",
            "status": "published",
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
            "model": DEFAULT_MODEL,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "enabled_tool_ids": DEFAULT_ENABLED_TOOLS,
            "allowed_scopes": DEFAULT_ALLOWED_SCOPES,
            "forked_from_version_id": None,
            "published_by": "migration",
            "published_at": now,
            "created_at": now,
            "updated_at": now,
        },
    )

    conn.execute(
        sa.update(agent_versions)
        .where(agent_versions.c.id == DEFAULT_VERSION_ID)
        .values(
            agent_id=DEFAULT_AGENT_ID,
            status="published",
            version_number=1,
            semantic_version="1.0.0",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            model=DEFAULT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
            enabled_tool_ids=DEFAULT_ENABLED_TOOLS,
            allowed_scopes=DEFAULT_ALLOWED_SCOPES,
            published_by="migration",
            published_at=now,
            updated_at=now,
        )
    )

    agent_runs = sa.table(
        "agent_runs",
        sa.column("id", sa.String(32)),
        sa.column("agent_id", sa.String(64)),
        sa.column("agent_version_id", sa.String(128)),
    )
    conn.execute(
        sa.update(agent_runs)
        .where(agent_runs.c.agent_id.is_(None))
        .values(agent_id=DEFAULT_AGENT_ID, agent_version_id=DEFAULT_VERSION_ID)
    )

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.alter_column("agent_id", nullable=False)
        batch_op.alter_column("agent_version_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_agent_runs_agent_id",
            "agents",
            ["agent_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_agent_runs_agent_version_id",
            "agent_versions",
            ["agent_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("fk_agent_runs_agent_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_agent_runs_agent_id", type_="foreignkey")
        batch_op.alter_column("agent_version_id", nullable=True)
        batch_op.alter_column("agent_id", nullable=True)
    op.drop_index("ix_agent_runs_agent_version_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_id", table_name="agent_runs")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("agent_version_id")
        batch_op.drop_column("agent_id")
