from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvalCaseRead(BaseModel):
    id: str
    scenario: str
    incident_id: str
    title: str
    expected_root_cause: str
    expected_evidence_types: list[str]
    expected_evidence: list[str]
    false_leads: list[str]
    recommended_actions: list[str]


class EvalResultRead(BaseModel):
    id: str
    eval_run_id: str
    eval_case_id: str
    agent_run_id: str
    scenario: str
    status: Literal["passed", "failed"]
    passed: bool
    root_cause_score: float
    citation_quality_score: float
    action_safety_score: float
    latency_ms: int
    expected_root_cause: str
    actual_root_cause: str | None
    expected_evidence_types: list[str]
    observed_evidence_types: list[str]
    failure_reasons: list[str]
    example_output: dict[str, Any]
    trace_id: str | None = None
    trace_url: str | None = None
    trace_provider: str | None = None
    started_at: datetime
    completed_at: datetime
    created_at: datetime


class EvalRunSummary(BaseModel):
    eval_run_id: str
    status: Literal["passed", "failed", "running"]
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    started_at: datetime
    completed_at: datetime | None = None
    results: list[EvalResultRead] = Field(default_factory=list)


class EvalResultsReport(BaseModel):
    latest_eval_run_id: str | None
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    results: list[EvalResultRead] = Field(default_factory=list)
