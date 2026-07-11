from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Agent, AgentRun, AgentVersion

from .schemas import AgentObservabilitySummary, AgentVersionObservability


def _p95_nearest_rank(values: list[int]) -> float | None:
    """Nearest-rank p95. ``rank = ceil(0.95 * N)`` (1-indexed), then take the
    value at that rank in the sorted-ascending list. Portable across Postgres
    and SQLite (no ``percentile_cont`` dependency, which is Postgres-only).

    With N=0 -> None. With N=1 -> that single value. With N=4 -> rank=4 -> the
    max, which is the conventional nearest-rank p95 for small samples.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(0.95 * len(ordered)))
    return float(ordered[rank - 1])


def _build_entry(
    *,
    agent_version_id: str,
    agent_id: str,
    agent_name: str,
    semantic_version: str | None,
    model: str,
    total_runs: int,
    successful_runs: int,
    total_cost: float,
    latencies: list[int],
    last_run_at: datetime | None,
) -> AgentVersionObservability:
    success_rate = round(successful_runs / total_runs, 4) if total_runs else 0.0
    avg_cost = round(total_cost / total_runs, 4) if total_runs else 0.0
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
    return AgentVersionObservability(
        agent_id=agent_id,
        agent_version_id=agent_version_id,
        agent_name=agent_name,
        semantic_version=semantic_version,
        model=model,
        total_runs=total_runs,
        successful_runs=successful_runs,
        success_rate=success_rate,
        avg_latency_ms=avg_latency,
        p95_latency_ms=_p95_nearest_rank(latencies),
        avg_cost_estimate_usd=avg_cost,
        total_cost_estimate_usd=round(total_cost, 4),
        last_run_at=last_run_at,
    )


def _version_aggregate_rows(
    session: Session, *, agent_id_filter: str | None
) -> list:
    """Per-version counts + cost sums + last-run timestamp, joined to the
    agent/version for labels. Portable SQL; latency is computed separately
    (datetime subtraction is not portable across Postgres/SQLite)."""
    query = (
        select(
            AgentRun.agent_version_id.label("agent_version_id"),
            AgentVersion.agent_id.label("agent_id"),
            Agent.name.label("agent_name"),
            AgentVersion.semantic_version.label("semantic_version"),
            AgentVersion.model.label("model"),
            func.count().label("total_runs"),
            func.count(
                case((AgentRun.status == "succeeded", 1), else_=None)
            ).label("successful_runs"),
            func.coalesce(
                func.sum(AgentRun.cost_estimate_usd), 0.0
            ).label("total_cost"),
            func.max(AgentRun.created_at).label("last_run_at"),
        )
        .select_from(AgentRun)
        .join(AgentVersion, AgentVersion.id == AgentRun.agent_version_id)
        .join(Agent, Agent.id == AgentVersion.agent_id)
        .group_by(
            AgentRun.agent_version_id,
            AgentVersion.agent_id,
            Agent.name,
            AgentVersion.semantic_version,
            AgentVersion.model,
            AgentVersion.version_number,
        )
        .order_by(
            Agent.name,
            AgentVersion.version_number.is_(None),
            AgentVersion.version_number,
            AgentRun.agent_version_id,
        )
    )
    if agent_id_filter is not None:
        query = query.where(AgentVersion.agent_id == agent_id_filter)
    return session.execute(query).all()


def _latencies_by_version(
    session: Session, *, agent_id_filter: str | None
) -> dict[str, list[int]]:
    """Per-version run latencies in ms for runs that have both timestamps
    (FR-19: p95 from ``completed_at - started_at``). Fetched and grouped in
    Python because datetime arithmetic in SQL is not portable across the
    Postgres (production) and SQLite (tests) backends."""
    query = select(
        AgentRun.agent_version_id,
        AgentRun.started_at,
        AgentRun.completed_at,
    ).where(
        AgentRun.started_at.is_not(None),
        AgentRun.completed_at.is_not(None),
    )
    if agent_id_filter is not None:
        query = query.join(
            AgentVersion, AgentVersion.id == AgentRun.agent_version_id
        ).where(AgentVersion.agent_id == agent_id_filter)

    latencies: dict[str, list[int]] = defaultdict(list)
    for row in session.execute(query).all():
        delta_ms = int(
            (row.completed_at - row.started_at).total_seconds() * 1000
        )
        latencies[row.agent_version_id].append(delta_ms)
    return latencies


def get_agent_version_dashboard(
    session: Session, *, agent_id: str | None = None
) -> list[AgentVersionObservability]:
    """Per-agent-version observability aggregates (PRD FR-19).

    When ``agent_id`` is None, every version that has runs is returned. When
    scoped to one agent, only that agent's versions are returned. An agent (or
    unknown agent id) with no runs yields an empty list — the dashboard is a
    run-driven aggregate, and absence of runs is a valid empty result.
    """
    rows = _version_aggregate_rows(session, agent_id_filter=agent_id)
    latencies = _latencies_by_version(session, agent_id_filter=agent_id)
    return [
        _build_entry(
            agent_version_id=row.agent_version_id,
            agent_id=row.agent_id,
            agent_name=row.agent_name,
            semantic_version=row.semantic_version,
            model=row.model,
            total_runs=int(row.total_runs or 0),
            successful_runs=int(row.successful_runs or 0),
            total_cost=float(row.total_cost or 0.0),
            latencies=latencies.get(row.agent_version_id, []),
            last_run_at=row.last_run_at,
        )
        for row in rows
    ]


def get_agent_dashboard(session: Session) -> list[AgentObservabilitySummary]:
    """Per-agent rollup across all versions (PRD §10: per-agent summary).

    Collapses every version's runs into one summary row per agent. Agents with
    no runs are not included (the dashboard is a run-driven aggregate). The
    per-version breakdown is available via ``get_agent_version_dashboard``.
    """
    version_rows = _version_aggregate_rows(session, agent_id_filter=None)
    latencies_by_version = _latencies_by_version(session, agent_id_filter=None)

    # Group per-version rows by agent_id, preserving the first-seen agent_name.
    agents: dict[str, dict[str, object]] = {}
    for row in version_rows:
        agent_bucket = agents.setdefault(
            row.agent_id,
            {
                "agent_id": row.agent_id,
                "agent_name": row.agent_name,
                "version_ids": set(),
                "total_runs": 0,
                "successful_runs": 0,
                "total_cost": 0.0,
                "latencies": [],
                "last_run_at": None,
            },
        )
        agent_bucket["version_ids"].add(row.agent_version_id)
        agent_bucket["total_runs"] += int(row.total_runs or 0)
        agent_bucket["successful_runs"] += int(row.successful_runs or 0)
        agent_bucket["total_cost"] += float(row.total_cost or 0.0)
        agent_bucket["latencies"].extend(
            latencies_by_version.get(row.agent_version_id, [])
        )
        row_last = row.last_run_at
        if row_last is not None:
            current_last = agent_bucket["last_run_at"]
            if current_last is None or row_last > current_last:
                agent_bucket["last_run_at"] = row_last

    summaries: list[AgentObservabilitySummary] = []
    for agent_data in agents.values():
        total_runs = int(agent_data["total_runs"])
        successful_runs = int(agent_data["successful_runs"])
        total_cost = float(agent_data["total_cost"])
        all_latencies: list[int] = agent_data["latencies"]  # type: ignore[assignment]
        success_rate = round(successful_runs / total_runs, 4) if total_runs else 0.0
        avg_cost = round(total_cost / total_runs, 4) if total_runs else 0.0
        avg_latency = (
            round(sum(all_latencies) / len(all_latencies), 2)
            if all_latencies
            else None
        )
        summaries.append(
            AgentObservabilitySummary(
                agent_id=agent_data["agent_id"],  # type: ignore[arg-type]
                agent_name=agent_data["agent_name"],  # type: ignore[arg-type]
                version_count=len(agent_data["version_ids"]),  # type: ignore[arg-type]
                total_runs=total_runs,
                successful_runs=successful_runs,
                success_rate=success_rate,
                avg_latency_ms=avg_latency,
                p95_latency_ms=_p95_nearest_rank(all_latencies),
                avg_cost_estimate_usd=avg_cost,
                total_cost_estimate_usd=round(total_cost, 4),
                last_run_at=agent_data["last_run_at"],  # type: ignore[arg-type]
            )
        )
    summaries.sort(key=lambda s: (s.agent_name, s.agent_id))
    return summaries
