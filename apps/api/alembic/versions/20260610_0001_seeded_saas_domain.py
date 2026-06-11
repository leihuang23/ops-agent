"""add seeded saas domain tables

Revision ID: 20260610_0001
Revises:
Create Date: 2026-06-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260610_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=False),
        sa.Column("industry", sa.String(length=80), nullable=False),
        sa.Column("region", sa.String(length=80), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("source_scenario", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accounts_segment"), "accounts", ["segment"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_account_id"), "users", ["account_id"], unique=False)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("plan", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("mrr_cents", sa.Integer(), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.Date(), nullable=False),
        sa.Column("canceled_at", sa.Date(), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=160), nullable=True),
        sa.Column("source_scenario", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subscriptions_account_id"),
        "subscriptions",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subscriptions_status"), "subscriptions", ["status"], unique=False
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("subscription_id", sa.String(length=32), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_reason", sa.String(length=160), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("source_scenario", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invoices_account_id"), "invoices", ["account_id"], unique=False
    )
    op.create_index("ix_invoices_account_date", "invoices", ["account_id", "invoice_date"])
    op.create_index(
        op.f("ix_invoices_invoice_date"), "invoices", ["invoice_date"], unique=False
    )
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)
    op.create_index(
        op.f("ix_invoices_subscription_id"),
        "invoices",
        ["subscription_id"],
        unique=False,
    )

    op.create_table(
        "product_events",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("source_scenario", sa.String(length=80), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_events_account_id"),
        "product_events",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_product_events_account_time",
        "product_events",
        ["account_id", "event_time"],
    )
    op.create_index(
        op.f("ix_product_events_event_name"),
        "product_events",
        ["event_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_events_event_time"),
        "product_events",
        ["event_time"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_events_source_scenario"),
        "product_events",
        ["source_scenario"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_events_user_id"),
        "product_events",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("source_scenario", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_support_tickets_account_id"),
        "support_tickets",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_support_tickets_account_created",
        "support_tickets",
        ["account_id", "created_at"],
    )
    op.create_index(
        op.f("ix_support_tickets_category"),
        "support_tickets",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_created_at"),
        "support_tickets",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_priority"),
        "support_tickets",
        ["priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_source_scenario"),
        "support_tickets",
        ["source_scenario"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_status"),
        "support_tickets",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_user_id"),
        "support_tickets",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_support_tickets_user_id"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_status"), table_name="support_tickets")
    op.drop_index(
        op.f("ix_support_tickets_source_scenario"), table_name="support_tickets"
    )
    op.drop_index(op.f("ix_support_tickets_priority"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_created_at"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_category"), table_name="support_tickets")
    op.drop_index("ix_support_tickets_account_created", table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_account_id"), table_name="support_tickets")
    op.drop_table("support_tickets")

    op.drop_index(op.f("ix_product_events_user_id"), table_name="product_events")
    op.drop_index(
        op.f("ix_product_events_source_scenario"), table_name="product_events"
    )
    op.drop_index(op.f("ix_product_events_event_time"), table_name="product_events")
    op.drop_index(op.f("ix_product_events_event_name"), table_name="product_events")
    op.drop_index("ix_product_events_account_time", table_name="product_events")
    op.drop_index(op.f("ix_product_events_account_id"), table_name="product_events")
    op.drop_table("product_events")

    op.drop_index(op.f("ix_invoices_subscription_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_invoice_date"), table_name="invoices")
    op.drop_index("ix_invoices_account_date", table_name="invoices")
    op.drop_index(op.f("ix_invoices_account_id"), table_name="invoices")
    op.drop_table("invoices")

    op.drop_index(op.f("ix_subscriptions_status"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_account_id"), table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index(op.f("ix_users_account_id"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_accounts_segment"), table_name="accounts")
    op.drop_table("accounts")
