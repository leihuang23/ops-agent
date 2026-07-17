"""Startup schema-compatibility probe.

Alembic tracks only a version string. If a database was stamped by a divergent
branch migration that reused a revision id, ``alembic upgrade head`` becomes a
silent no-op while the actual schema lags behind the models, and startup then
crashes deep inside ORM code with an opaque ``UndefinedColumn`` error.

This module checks a curated set of tables and columns that the startup path
(bootstrap, seed repair, orphan reaper) depends on, so drift fails fast with
an actionable message. Portable across SQLite (tests) and PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

# (table, required columns) — the schema surface startup code touches. Keep
# this in sync with the latest migrations when bootstrap dependencies grow.
REQUIRED_SCHEMA: Sequence[tuple[str, Sequence[str]]] = (
    ("agents", ("id", "name")),
    (
        "agent_versions",
        ("id", "agent_id", "status", "enabled_tool_ids", "allowed_scopes"),
    ),
    (
        "tools",
        (
            "id",
            "permission_scope",
            "implementation_ref",
            "created_at",
            "updated_at",
        ),
    ),
    ("agent_runs", ("id", "status", "agent_version_id")),
    ("agent_run_steps", ("id", "run_id", "sequence", "blocked_reason")),
    ("model_usage", ("id", "run_id")),
    ("eval_datasets", ("id", "name")),
    ("eval_dataset_cases", ("dataset_id", "eval_case_id")),
)


def find_missing_schema(engine: Engine) -> list[str]:
    """Return human-readable entries for each missing table/column.

    An empty list means the schema surface required at startup is present.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing: list[str] = []
    for table, columns in REQUIRED_SCHEMA:
        if table not in existing_tables:
            missing.append(f"table {table} is missing")
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table)}
        for column in columns:
            if column not in existing_columns:
                missing.append(f"column {table}.{column} is missing")
    return missing


def assert_schema_compatible(engine: Engine) -> None:
    """Fail fast when the database schema is behind the application models."""
    missing = find_missing_schema(engine)
    if not missing:
        return
    details = "; ".join(missing)
    raise SystemExit(
        "Database schema is behind the application models "
        f"({details}). This usually means alembic_version was stamped by a "
        "divergent branch migration that reused a revision id, so "
        "`alembic upgrade head` is a no-op. Repair with "
        "`alembic stamp <previous_revision> && alembic upgrade head` against "
        "the affected database, or reset the demo database."
    )
