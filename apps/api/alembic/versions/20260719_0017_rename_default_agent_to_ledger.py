"""rename the default agent identity to Ledger

Revision ID: 20260719_0017
Revises: 20260710_0016
Create Date: 2026-07-19 00:00:00.000000

The product rename changes persisted default-agent and immutable-version keys.
Existing migrations remain untouched. This revision copies the identity graph
to its new keys, repoints every foreign-key reference, and then removes the old
rows. The downgrade performs the inverse operation.
"""

from collections.abc import Callable, Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260719_0017"
down_revision: str | None = "20260710_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_AGENT_ID = "revenue-ops-agent"
LEDGER_AGENT_ID = "ledger"
LEGACY_AGENT_NAME = "Revenue Ops Agent"
LEDGER_AGENT_NAME = "Ledger"


def _tables() -> tuple[sa.TableClause, ...]:
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
        sa.column("published_at", sa.DateTime),
        sa.column("published_by", sa.String(80)),
        sa.column("forked_from_version_id", sa.String(128)),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    agent_runs = sa.table(
        "agent_runs",
        sa.column("agent_id", sa.String(64)),
        sa.column("agent_version_id", sa.String(128)),
    )
    eval_results = sa.table(
        "eval_results",
        sa.column("agent_version_id", sa.String(128)),
    )
    return agents, agent_versions, agent_runs, eval_results


def _upgrade_version_id(version_id: str) -> str:
    prefix = f"{LEGACY_AGENT_ID}_"
    if version_id.startswith(prefix):
        return f"{LEDGER_AGENT_ID}_{version_id.removeprefix(prefix)}"
    return f"{LEDGER_AGENT_ID}_legacy_{version_id}"


def _downgrade_version_id(version_id: str) -> str:
    legacy_prefix = f"{LEDGER_AGENT_ID}_legacy_"
    if version_id.startswith(legacy_prefix):
        return version_id.removeprefix(legacy_prefix)
    prefix = f"{LEDGER_AGENT_ID}_"
    if version_id.startswith(prefix):
        return f"{LEGACY_AGENT_ID}_{version_id.removeprefix(prefix)}"
    raise RuntimeError(
        f"Cannot downgrade Ledger version key {version_id!r}: unsupported format."
    )


def _rename_identity(
    *,
    source_agent_id: str,
    target_agent_id: str,
    target_agent_name: str,
    map_version_id: Callable[[str], str],
) -> None:
    conn = op.get_bind()
    agents, agent_versions, agent_runs, eval_results = _tables()

    source_agent = conn.execute(
        sa.select(agents).where(agents.c.id == source_agent_id)
    ).mappings().one_or_none()
    if source_agent is None:
        raise RuntimeError(
            f"Cannot rename agent {source_agent_id!r}: source row does not exist."
        )
    if conn.execute(
        sa.select(agents.c.id).where(agents.c.id == target_agent_id)
    ).first() is not None:
        raise RuntimeError(
            f"Cannot rename agent {source_agent_id!r}: destination "
            f"{target_agent_id!r} already exists."
        )

    source_versions = list(
        conn.execute(
            sa.select(agent_versions)
            .where(agent_versions.c.agent_id == source_agent_id)
            .order_by(agent_versions.c.created_at, agent_versions.c.id)
        ).mappings()
    )
    version_ids = {
        row["id"]: map_version_id(row["id"])
        for row in source_versions
    }
    if len(set(version_ids.values())) != len(version_ids):
        raise RuntimeError("Cannot rename agent versions: destination keys collide.")
    conflicting_ids = set(
        conn.scalars(
            sa.select(agent_versions.c.id).where(
                agent_versions.c.id.in_(tuple(version_ids.values()))
            )
        )
    )
    if conflicting_ids:
        raise RuntimeError(
            "Cannot rename agent versions: destination keys already exist: "
            + ", ".join(sorted(conflicting_ids))
        )

    conn.execute(
        agents.insert().values(
            id=target_agent_id,
            name=target_agent_name,
            description=source_agent["description"],
            default_model=source_agent["default_model"],
            created_at=source_agent["created_at"],
            updated_at=source_agent["updated_at"],
        )
    )

    for source_version in source_versions:
        values = dict(source_version)
        values.update(
            id=version_ids[source_version["id"]],
            agent_id=target_agent_id,
            forked_from_version_id=None,
        )
        conn.execute(agent_versions.insert().values(**values))

    for source_version in source_versions:
        source_fork_id = source_version["forked_from_version_id"]
        if source_fork_id is None:
            continue
        target_fork_id = version_ids.get(source_fork_id, source_fork_id)
        conn.execute(
            agent_versions.update()
            .where(agent_versions.c.id == version_ids[source_version["id"]])
            .values(forked_from_version_id=target_fork_id)
        )

    for source_version_id, target_version_id in version_ids.items():
        conn.execute(
            agent_versions.update()
            .where(
                agent_versions.c.forked_from_version_id == source_version_id,
                agent_versions.c.agent_id != source_agent_id,
            )
            .values(forked_from_version_id=target_version_id)
        )
        conn.execute(
            agent_runs.update()
            .where(agent_runs.c.agent_version_id == source_version_id)
            .values(agent_version_id=target_version_id)
        )
        conn.execute(
            eval_results.update()
            .where(eval_results.c.agent_version_id == source_version_id)
            .values(agent_version_id=target_version_id)
        )

    conn.execute(
        agent_runs.update()
        .where(agent_runs.c.agent_id == source_agent_id)
        .values(agent_id=target_agent_id)
    )
    if version_ids:
        conn.execute(
            agent_versions.delete().where(
                agent_versions.c.id.in_(tuple(version_ids.keys()))
            )
        )
    conn.execute(agents.delete().where(agents.c.id == source_agent_id))


def upgrade() -> None:
    _rename_identity(
        source_agent_id=LEGACY_AGENT_ID,
        target_agent_id=LEDGER_AGENT_ID,
        target_agent_name=LEDGER_AGENT_NAME,
        map_version_id=_upgrade_version_id,
    )


def downgrade() -> None:
    _rename_identity(
        source_agent_id=LEDGER_AGENT_ID,
        target_agent_id=LEGACY_AGENT_ID,
        target_agent_name=LEGACY_AGENT_NAME,
        map_version_id=_downgrade_version_id,
    )
