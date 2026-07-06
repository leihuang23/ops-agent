"""add composite indexes for invoice and subscription hot paths

Revision ID: 20260706_0009
Revises: 20260705_0008
Create Date: 2026-07-06 00:00:00.000000

These composite indexes support the dashboard and anomaly-detection queries
that filter by status and then order or range-filter by a date column:

- invoices(status, invoice_date): backs get_failed_invoice_metrics, which
  filters on status = 'failed' and invoice_date >= cutoff.
- subscriptions(status, canceled_at): backs get_churn_metrics, which filters
  on status = 'canceled' and inspects canceled_at.

The single-column indexes on status / invoice_date / canceled_at remain in
place; these composite indexes are additive and only accelerate the combined
predicate that the metric functions actually issue.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260706_0009"
down_revision: str | None = "20260705_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_invoices_status_invoice_date",
        "invoices",
        ["status", "invoice_date"],
        unique=False,
    )
    op.create_index(
        "ix_subscriptions_status_canceled_at",
        "subscriptions",
        ["status", "canceled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_subscriptions_status_canceled_at", table_name="subscriptions")
    op.drop_index("ix_invoices_status_invoice_date", table_name="invoices")
