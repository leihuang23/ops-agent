"""evaluation studio datasets, versioned results, and approval-active run guard

Revision ID: 20260710_0014
Revises: 20260710_0013
Create Date: 2026-07-10 00:00:00.000000

Phase 5 adds dataset grouping and version-attributed eval result fields without
rewriting Project 1 rows. Existing results retain nullable dataset/version
links and receive a zero cost estimate. The active-incident uniqueness guard
also treats ``waiting_for_approval`` as active so a paused run cannot be
bypassed by launching a second investigation for the same incident.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260710_0014"
down_revision: str | None = "20260710_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_active_incident_index(*, include_waiting: bool) -> None:
    statuses = (
        "'queued', 'running', 'waiting_for_approval'"
        if include_waiting
        else "'queued', 'running'"
    )
    predicate = sa.text(f"status IN ({statuses})")
    op.create_index(
        "uq_agent_runs_active_incident",
        "agent_runs",
        ["incident_id"],
        unique=True,
        sqlite_where=predicate,
        postgresql_where=predicate,
    )


def upgrade() -> None:
    op.create_table(
        "eval_datasets",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_eval_datasets")),
    )
    op.create_index(
        op.f("ix_eval_datasets_name"),
        "eval_datasets",
        ["name"],
        unique=True,
    )
    op.create_table(
        "eval_dataset_cases",
        sa.Column("dataset_id", sa.String(length=80), nullable=False),
        sa.Column("eval_case_id", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["eval_datasets.id"],
            name=op.f("fk_eval_dataset_cases_dataset_id_eval_datasets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["eval_case_id"],
            ["eval_cases.id"],
            name=op.f("fk_eval_dataset_cases_eval_case_id_eval_cases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "dataset_id", "eval_case_id", name=op.f("pk_eval_dataset_cases")
        ),
    )

    with op.batch_alter_table("eval_results") as batch_op:
        batch_op.add_column(
            sa.Column("agent_version_id", sa.String(length=128), nullable=True)
        )
        batch_op.add_column(
            sa.Column("dataset_id", sa.String(length=80), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "cost_estimate_usd",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            )
        )
        batch_op.create_foreign_key(
            op.f("fk_eval_results_agent_version_id_agent_versions"),
            "agent_versions",
            ["agent_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            op.f("fk_eval_results_dataset_id_eval_datasets"),
            "eval_datasets",
            ["dataset_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        op.f("ix_eval_results_agent_version_id"),
        "eval_results",
        ["agent_version_id"],
    )
    op.create_index(
        op.f("ix_eval_results_dataset_id"), "eval_results", ["dataset_id"]
    )
    op.create_index(
        "ix_eval_results_version_dataset_created",
        "eval_results",
        ["agent_version_id", "dataset_id", "created_at"],
    )

    op.drop_index("uq_agent_runs_active_incident", table_name="agent_runs")
    _create_active_incident_index(include_waiting=True)


def downgrade() -> None:
    op.drop_index("uq_agent_runs_active_incident", table_name="agent_runs")
    _create_active_incident_index(include_waiting=False)

    op.drop_index(
        "ix_eval_results_version_dataset_created", table_name="eval_results"
    )
    op.drop_index(op.f("ix_eval_results_dataset_id"), table_name="eval_results")
    op.drop_index(
        op.f("ix_eval_results_agent_version_id"), table_name="eval_results"
    )
    with op.batch_alter_table("eval_results") as batch_op:
        batch_op.drop_constraint(
            op.f("fk_eval_results_dataset_id_eval_datasets"), type_="foreignkey"
        )
        batch_op.drop_constraint(
            op.f("fk_eval_results_agent_version_id_agent_versions"),
            type_="foreignkey",
        )
        batch_op.drop_column("cost_estimate_usd")
        batch_op.drop_column("dataset_id")
        batch_op.drop_column("agent_version_id")

    op.drop_table("eval_dataset_cases")
    op.drop_index(op.f("ix_eval_datasets_name"), table_name="eval_datasets")
    op.drop_table("eval_datasets")
