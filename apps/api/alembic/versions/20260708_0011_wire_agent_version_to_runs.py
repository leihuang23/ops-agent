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
import json

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
VALID_MODELS = {
    "gpt-4o-mini",
    "gpt-4o",
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-haiku-20240307",
}
EVIDENCE_PRODUCING_TOOL_IDS = {
    "query_revenue_metrics",
    "search_docs",
    "fetch_support_tickets",
}


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


def _as_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return []


def _has_publishable_config(row: sa.engine.Row | None) -> bool:
    if row is None:
        return False
    return (
        row.status == "published"
        and row.model in VALID_MODELS
        and bool(set(_as_list(row.enabled_tool_ids)) & EVIDENCE_PRODUCING_TOOL_IDS)
    )


def _is_publishable_version(row: sa.engine.Row | None) -> bool:
    return _has_publishable_config(row) and row.version_number is not None


def _next_published_version_number(
    conn: sa.engine.Connection,
    agent_versions: sa.TableClause,
) -> int:
    used_numbers = conn.execute(
        sa.select(agent_versions.c.version_number).where(
            agent_versions.c.agent_id == DEFAULT_AGENT_ID,
            agent_versions.c.status == "published",
            agent_versions.c.id != DEFAULT_VERSION_ID,
            agent_versions.c.version_number.is_not(None),
        )
    ).scalars()
    used = {number for number in used_numbers if isinstance(number, int)}
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


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
    op.drop_index("uq_agent_runs_active_incident", table_name="agent_runs")

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
    existing_default_version = conn.execute(
        sa.select(
            agent_versions.c.id,
            agent_versions.c.status,
            agent_versions.c.version_number,
            agent_versions.c.model,
            agent_versions.c.enabled_tool_ids,
        ).where(agent_versions.c.id == DEFAULT_VERSION_ID)
    ).first()
    existing_published_versions = conn.execute(
        sa.select(
            agent_versions.c.id,
            agent_versions.c.status,
            agent_versions.c.version_number,
            agent_versions.c.model,
            agent_versions.c.enabled_tool_ids,
        )
        .where(
            agent_versions.c.agent_id == DEFAULT_AGENT_ID,
            agent_versions.c.status == "published",
        )
        .order_by(
            sa.func.coalesce(agent_versions.c.version_number, 0).desc(),
            agent_versions.c.published_at.desc(),
            agent_versions.c.id.desc(),
        )
    ).all()
    existing_published_version = next(
        (
            version
            for version in existing_published_versions
            if _is_publishable_version(version)
        ),
        None,
    )

    if (
        existing_default_version is not None
        and _has_publishable_config(existing_default_version)
        and existing_default_version.version_number is None
    ):
        conn.execute(
            agent_versions.update()
            .where(agent_versions.c.id == DEFAULT_VERSION_ID)
            .values(
                semantic_version=sa.func.coalesce(
                    agent_versions.c.semantic_version,
                    "legacy",
                ),
                published_at=sa.func.coalesce(agent_versions.c.published_at, now),
                updated_at=now,
            )
        )
        existing_default_version = conn.execute(
            sa.select(
                agent_versions.c.id,
                agent_versions.c.status,
                agent_versions.c.version_number,
                agent_versions.c.model,
                agent_versions.c.enabled_tool_ids,
            ).where(agent_versions.c.id == DEFAULT_VERSION_ID)
        ).first()

    default_needs_repair = (
        existing_default_version is not None
        and not _has_publishable_config(existing_default_version)
    )
    if default_needs_repair:
        repaired_version_number = _next_published_version_number(conn, agent_versions)
        conn.execute(
            agent_versions.update()
            .where(agent_versions.c.id == DEFAULT_VERSION_ID)
            .values(
                agent_id=DEFAULT_AGENT_ID,
                version_number=repaired_version_number,
                semantic_version=f"{repaired_version_number}.0.0",
                status="published",
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
        existing_default_version = conn.execute(
            sa.select(
                agent_versions.c.id,
                agent_versions.c.status,
                agent_versions.c.version_number,
                agent_versions.c.model,
                agent_versions.c.enabled_tool_ids,
            ).where(agent_versions.c.id == DEFAULT_VERSION_ID)
        ).first()

    if existing_default_version is None:
        new_version_number = _next_published_version_number(conn, agent_versions)
        conn.execute(
            agent_versions.insert().values(
                id=DEFAULT_VERSION_ID,
                agent_id=DEFAULT_AGENT_ID,
                version_number=new_version_number,
                semantic_version=f"{new_version_number}.0.0",
                status="published",
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                model=DEFAULT_MODEL,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS,
                enabled_tool_ids=DEFAULT_ENABLED_TOOLS,
                allowed_scopes=DEFAULT_ALLOWED_SCOPES,
                forked_from_version_id=None,
                published_by="migration",
                published_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        existing_default_version = conn.execute(
            sa.select(
                agent_versions.c.id,
                agent_versions.c.status,
                agent_versions.c.version_number,
                agent_versions.c.model,
                agent_versions.c.enabled_tool_ids,
            ).where(agent_versions.c.id == DEFAULT_VERSION_ID)
        ).first()

    backfill_version_id = DEFAULT_VERSION_ID
    if _has_publishable_config(existing_default_version):
        backfill_version_id = DEFAULT_VERSION_ID
    elif existing_published_version is not None:
        backfill_version_id = existing_published_version.id

    agent_runs = sa.table(
        "agent_runs",
        sa.column("id", sa.String(32)),
        sa.column("agent_id", sa.String(64)),
        sa.column("agent_version_id", sa.String(128)),
    )
    conn.execute(
        sa.update(agent_runs)
        .where(sa.or_(agent_runs.c.agent_id.is_(None), agent_runs.c.agent_version_id.is_(None)))
        .values(agent_id=DEFAULT_AGENT_ID, agent_version_id=backfill_version_id)
    )
    op.create_index(
        "uq_agent_runs_active_incident",
        "agent_runs",
        ["incident_id", "agent_version_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
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
    op.drop_index("uq_agent_runs_active_incident", table_name="agent_runs")
    op.execute(
        sa.text(
            """
            UPDATE agent_runs
            SET
                status = 'failed',
                error = COALESCE(error, 'Investigation interrupted before completion.'),
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY incident_id
                            ORDER BY created_at DESC, id DESC
                        ) AS active_rank
                    FROM agent_runs
                    WHERE status IN ('queued', 'running')
                ) ranked_active_runs
                WHERE active_rank > 1
            )
            """
        )
    )
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint("fk_agent_runs_agent_version_id", type_="foreignkey")
        batch_op.drop_constraint("fk_agent_runs_agent_id", type_="foreignkey")
        batch_op.alter_column("agent_version_id", nullable=True)
        batch_op.alter_column("agent_id", nullable=True)
    op.drop_index("ix_agent_runs_agent_version_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_id", table_name="agent_runs")
    op.create_index(
        "uq_agent_runs_active_incident",
        "agent_runs",
        ["incident_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("agent_version_id")
        batch_op.drop_column("agent_id")
