from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


class EvalDatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    case_ids: list[str] = Field(min_length=1, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EvalDatasetSummary(BaseModel):
    id: str
    name: str
    description: str
    case_count: int
    created_at: datetime
    updated_at: datetime


class EvalDatasetDetail(BaseModel):
    id: str
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    cases: list[EvalCaseRead]


class EvalDatasetList(BaseModel):
    datasets: list[EvalDatasetSummary]
    total: int


class EvalDatasetRunRequest(BaseModel):
    agent_version_id: str = Field(min_length=1, max_length=128)


class EvalDatasetRunAccepted(BaseModel):
    eval_run_id: str
    dataset_id: str
    agent_version_id: str
    status: Literal["queued"] = "queued"


class EvalResultRead(BaseModel):
    id: str
    eval_run_id: str
    eval_case_id: str
    agent_run_id: str
    agent_version_id: str | None = None
    dataset_id: str | None = None
    scenario: str
    status: Literal["passed", "failed"]
    passed: bool
    root_cause_score: float
    citation_quality_score: float
    action_safety_score: float
    latency_ms: int
    cost_estimate_usd: float = 0.0
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


class EvalResultList(BaseModel):
    results: list[EvalResultRead]
    total: int


class EvalCaseComparison(BaseModel):
    eval_case_id: str
    scenario: str
    result_a_id: str
    result_b_id: str
    passed_a: bool
    passed_b: bool
    change: Literal["regression", "improvement", "unchanged"]


class EvalVersionComparison(BaseModel):
    version_a: str
    version_b: str
    dataset_id: str
    run_a_id: str
    run_b_id: str
    pass_rate_a: float
    pass_rate_b: float
    pass_rate_delta: float
    total_cases: int
    cases: list[EvalCaseComparison]
    regressions: list[EvalCaseComparison]
    improvements: list[EvalCaseComparison]
