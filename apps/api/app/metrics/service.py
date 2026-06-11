from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Invoice, ProductEvent, Subscription, SupportTicket
from app.seed import DATASET_ANCHOR

from .schemas import (
    ActiveUserMetrics,
    CategoryCount,
    ChurnMetrics,
    DashboardMetrics,
    FailedInvoiceMetrics,
    FailedInvoiceSample,
    MrrMetrics,
    TicketVolumeMetrics,
)


def get_dataset_anchor(session: Session) -> datetime:
    anchor = session.scalar(select(func.max(ProductEvent.event_time)))
    return anchor or DATASET_ANCHOR


def get_mrr_metrics(session: Session, anchor: datetime | None = None) -> MrrMetrics:
    anchor = anchor or get_dataset_anchor(session)
    churn_cutoff = anchor.date() - timedelta(days=30)

    current_mrr = int(
        session.scalar(
            select(func.coalesce(func.sum(Subscription.mrr_cents), 0)).where(
                Subscription.status == "active"
            )
        )
        or 0
    )
    previous_churned_mrr = int(
        session.scalar(
            select(func.coalesce(func.sum(Subscription.mrr_cents), 0)).where(
                Subscription.status == "canceled",
                Subscription.canceled_at >= churn_cutoff,
            )
        )
        or 0
    )
    active_subscriptions = int(
        session.scalar(
            select(func.count()).select_from(Subscription).where(
                Subscription.status == "active"
            )
        )
        or 0
    )
    previous_mrr = current_mrr + previous_churned_mrr
    delta_cents = current_mrr - previous_mrr
    delta_percent = round((delta_cents / previous_mrr) * 100, 2) if previous_mrr else 0.0

    return MrrMetrics(
        current_mrr_cents=current_mrr,
        previous_mrr_cents=previous_mrr,
        delta_cents=delta_cents,
        delta_percent=delta_percent,
        active_subscriptions=active_subscriptions,
        churned_mrr_cents=previous_churned_mrr,
    )


def get_churn_metrics(session: Session, anchor: datetime | None = None) -> ChurnMetrics:
    anchor = anchor or get_dataset_anchor(session)
    churn_cutoff = anchor.date() - timedelta(days=30)

    active_accounts = int(
        session.scalar(
            select(func.count()).select_from(Subscription).where(
                Subscription.status == "active"
            )
        )
        or 0
    )
    churned_accounts = int(
        session.scalar(
            select(func.count()).select_from(Subscription).where(
                Subscription.status == "canceled",
                Subscription.canceled_at >= churn_cutoff,
            )
        )
        or 0
    )
    churned_mrr = int(
        session.scalar(
            select(func.coalesce(func.sum(Subscription.mrr_cents), 0)).where(
                Subscription.status == "canceled",
                Subscription.canceled_at >= churn_cutoff,
            )
        )
        or 0
    )
    denominator = active_accounts + churned_accounts
    churn_rate = round(churned_accounts / denominator, 4) if denominator else 0.0

    return ChurnMetrics(
        churned_accounts_30d=churned_accounts,
        active_accounts=active_accounts,
        churn_rate_30d=churn_rate,
        churned_mrr_cents_30d=churned_mrr,
    )


def get_failed_invoice_metrics(
    session: Session, anchor: datetime | None = None
) -> FailedInvoiceMetrics:
    anchor = anchor or get_dataset_anchor(session)
    cutoff = anchor.date() - timedelta(days=30)

    failed_count = int(
        session.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.status == "failed",
                Invoice.invoice_date >= cutoff,
            )
        )
        or 0
    )
    failed_amount = int(
        session.scalar(
            select(func.coalesce(func.sum(Invoice.amount_cents), 0)).where(
                Invoice.status == "failed",
                Invoice.invoice_date >= cutoff,
            )
        )
        or 0
    )
    unresolved_count = int(
        session.scalar(
            select(func.count()).select_from(Invoice).where(
                Invoice.status == "failed",
                Invoice.invoice_date >= cutoff,
            )
        )
        or 0
    )
    rows = session.execute(
        select(
            Invoice.id,
            Account.name,
            Invoice.invoice_date,
            Invoice.amount_cents,
            Invoice.failure_reason,
            Invoice.source_scenario,
        )
        .join(Account, Account.id == Invoice.account_id)
        .where(Invoice.status == "failed", Invoice.invoice_date >= cutoff)
        .order_by(Invoice.invoice_date.desc(), Invoice.amount_cents.desc(), Invoice.id)
        .limit(8)
    ).all()

    return FailedInvoiceMetrics(
        failed_count_30d=failed_count,
        failed_amount_cents_30d=failed_amount,
        unresolved_count_30d=unresolved_count,
        recent_failures=[
            FailedInvoiceSample(
                invoice_id=row.id,
                account_name=row.name,
                invoice_date=row.invoice_date,
                amount_cents=row.amount_cents,
                failure_reason=row.failure_reason,
                source_scenario=row.source_scenario,
            )
            for row in rows
        ],
    )


def get_ticket_volume_metrics(
    session: Session, anchor: datetime | None = None
) -> TicketVolumeMetrics:
    anchor = anchor or get_dataset_anchor(session)
    cutoff = anchor - timedelta(days=30)

    total_30d = int(
        session.scalar(
            select(func.count()).select_from(SupportTicket).where(
                SupportTicket.created_at >= cutoff
            )
        )
        or 0
    )
    open_tickets = int(
        session.scalar(
            select(func.count()).select_from(SupportTicket).where(
                SupportTicket.status.in_(("open", "pending"))
            )
        )
        or 0
    )
    high_priority_open = int(
        session.scalar(
            select(func.count()).select_from(SupportTicket).where(
                SupportTicket.status.in_(("open", "pending")),
                SupportTicket.priority == "high",
            )
        )
        or 0
    )
    rows = session.execute(
        select(SupportTicket.category, func.count().label("count"))
        .where(SupportTicket.created_at >= cutoff)
        .group_by(SupportTicket.category)
        .order_by(func.count().desc(), SupportTicket.category)
    ).all()

    return TicketVolumeMetrics(
        total_tickets_30d=total_30d,
        open_tickets=open_tickets,
        high_priority_open_tickets=high_priority_open,
        by_category_30d=[
            CategoryCount(category=row.category, count=row.count) for row in rows
        ],
    )


def get_active_user_metrics(
    session: Session, anchor: datetime | None = None
) -> ActiveUserMetrics:
    anchor = anchor or get_dataset_anchor(session)
    cutoff_7d = anchor - timedelta(days=7)
    cutoff_30d = anchor - timedelta(days=30)

    active_users_7d = int(
        session.scalar(
            select(func.count(func.distinct(ProductEvent.user_id))).where(
                ProductEvent.event_time >= cutoff_7d
            )
        )
        or 0
    )
    active_users_30d = int(
        session.scalar(
            select(func.count(func.distinct(ProductEvent.user_id))).where(
                ProductEvent.event_time >= cutoff_30d
            )
        )
        or 0
    )
    event_count_7d = int(
        session.scalar(
            select(func.count()).select_from(ProductEvent).where(
                ProductEvent.event_time >= cutoff_7d
            )
        )
        or 0
    )
    event_count_30d = int(
        session.scalar(
            select(func.count()).select_from(ProductEvent).where(
                ProductEvent.event_time >= cutoff_30d
            )
        )
        or 0
    )

    return ActiveUserMetrics(
        active_users_7d=active_users_7d,
        active_users_30d=active_users_30d,
        event_count_7d=event_count_7d,
        event_count_30d=event_count_30d,
    )


def get_dashboard_metrics(session: Session) -> DashboardMetrics:
    anchor = get_dataset_anchor(session)
    return DashboardMetrics(
        as_of=anchor,
        mrr=get_mrr_metrics(session, anchor),
        churn=get_churn_metrics(session, anchor),
        failed_invoices=get_failed_invoice_metrics(session, anchor),
        ticket_volume=get_ticket_volume_metrics(session, anchor),
        active_users=get_active_user_metrics(session, anchor),
    )
