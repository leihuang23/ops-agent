"""add observability trace metadata and eval suite

Revision ID: 20260625_0006
Revises: 20260624_0005
Create Date: 2026-06-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260625_0006"
down_revision: str | None = "20260624_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("trace_url", sa.String(length=512), nullable=True))
    op.add_column("agent_runs", sa.Column("trace_provider", sa.String(length=32), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("trace_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(
        op.f("ix_agent_runs_trace_provider"),
        "agent_runs",
        ["trace_provider"],
        unique=False,
    )
    op.alter_column("agent_runs", "trace_metadata", server_default=None)

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("scenario", sa.String(length=80), nullable=False),
        sa.Column("incident_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("expected_root_cause", sa.Text(), nullable=False),
        sa.Column("expected_evidence_types", sa.JSON(), nullable=False),
        sa.Column("expected_evidence", sa.JSON(), nullable=False),
        sa.Column("false_leads", sa.JSON(), nullable=False),
        sa.Column("recommended_actions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_cases_incident_id"), "eval_cases", ["incident_id"])
    op.create_index(op.f("ix_eval_cases_scenario"), "eval_cases", ["scenario"], unique=True)

    op.create_table(
        "eval_results",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("eval_run_id", sa.String(length=80), nullable=False),
        sa.Column("eval_case_id", sa.String(length=80), nullable=False),
        sa.Column("agent_run_id", sa.String(length=48), nullable=False),
        sa.Column("scenario", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("root_cause_score", sa.Float(), nullable=False),
        sa.Column("citation_quality_score", sa.Float(), nullable=False),
        sa.Column("action_safety_score", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("expected_root_cause", sa.Text(), nullable=False),
        sa.Column("actual_root_cause", sa.Text(), nullable=True),
        sa.Column("expected_evidence_types", sa.JSON(), nullable=False),
        sa.Column("observed_evidence_types", sa.JSON(), nullable=False),
        sa.Column("failure_reasons", sa.JSON(), nullable=False),
        sa.Column("example_output", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["eval_case_id"], ["eval_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eval_results_agent_run_id"), "eval_results", ["agent_run_id"])
    op.create_index(op.f("ix_eval_results_eval_case_id"), "eval_results", ["eval_case_id"])
    op.create_index(op.f("ix_eval_results_eval_run_id"), "eval_results", ["eval_run_id"])
    op.create_index(op.f("ix_eval_results_passed"), "eval_results", ["passed"])
    op.create_index(op.f("ix_eval_results_scenario"), "eval_results", ["scenario"])
    op.create_index(op.f("ix_eval_results_status"), "eval_results", ["status"])
    op.create_index("ix_eval_results_run_case", "eval_results", ["eval_run_id", "eval_case_id"])
    op.create_index(
        "ix_eval_results_case_created",
        "eval_results",
        ["eval_case_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_eval_results_case_created", table_name="eval_results")
    op.drop_index("ix_eval_results_run_case", table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_status"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_scenario"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_passed"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_eval_run_id"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_eval_case_id"), table_name="eval_results")
    op.drop_index(op.f("ix_eval_results_agent_run_id"), table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_index(op.f("ix_eval_cases_scenario"), table_name="eval_cases")
    op.drop_index(op.f("ix_eval_cases_incident_id"), table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index(op.f("ix_agent_runs_trace_provider"), table_name="agent_runs")
    op.drop_column("agent_runs", "trace_metadata")
    op.drop_column("agent_runs", "trace_provider")
    op.drop_column("agent_runs", "trace_url")
