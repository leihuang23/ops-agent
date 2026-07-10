from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.agent.persistence import utcnow_naive
from app.evals.schemas import (
    EvalCaseRead,
    EvalDatasetCreate,
    EvalDatasetDetail,
    EvalDatasetList,
    EvalDatasetSummary,
    EvalCaseComparison,
    EvalResultList,
    EvalVersionComparison,
)
from app.evals.runner import eval_result_to_read
from app.models import EvalCase, EvalDataset, EvalDatasetCase, EvalResult


class DuplicateDatasetNameError(ValueError):
    pass


class InvalidDatasetCasesError(ValueError):
    pass


def _case_read(case: EvalCase) -> EvalCaseRead:
    return EvalCaseRead(
        id=case.id,
        scenario=case.scenario,
        incident_id=case.incident_id,
        title=case.title,
        expected_root_cause=case.expected_root_cause,
        expected_evidence_types=list(case.expected_evidence_types),
        expected_evidence=list(case.expected_evidence),
        false_leads=list(case.false_leads),
        recommended_actions=list(case.recommended_actions),
    )


def _dataset_detail(dataset: EvalDataset) -> EvalDatasetDetail:
    cases = [link.eval_case for link in dataset.case_links]
    return EvalDatasetDetail(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        cases=[_case_read(case) for case in cases],
    )


def create_eval_dataset(
    session: Session, payload: EvalDatasetCreate
) -> EvalDatasetDetail:
    case_ids = list(dict.fromkeys(payload.case_ids))
    if len(case_ids) != len(payload.case_ids):
        raise InvalidDatasetCasesError("case_ids must not contain duplicates")
    cases = session.scalars(
        select(EvalCase).where(EvalCase.id.in_(case_ids))
    ).all()
    cases_by_id = {case.id: case for case in cases}
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise InvalidDatasetCasesError(
            "Unknown eval case ids: " + ", ".join(missing)
        )

    now = utcnow_naive()
    dataset = EvalDataset(
        id=f"evalds_{uuid4().hex[:16]}",
        name=payload.name.strip(),
        description=payload.description.strip(),
        created_at=now,
        updated_at=now,
    )
    dataset.case_links = [
        EvalDatasetCase(eval_case=cases_by_id[case_id]) for case_id in case_ids
    ]
    session.add(dataset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateDatasetNameError(
            f"An eval dataset named {dataset.name!r} already exists"
        ) from exc
    session.refresh(dataset)
    return _dataset_detail(dataset)


def list_eval_datasets(session: Session) -> EvalDatasetList:
    rows = session.execute(
        select(EvalDataset, func.count(EvalDatasetCase.eval_case_id))
        .outerjoin(EvalDatasetCase, EvalDatasetCase.dataset_id == EvalDataset.id)
        .group_by(EvalDataset.id)
        .order_by(EvalDataset.name, EvalDataset.id)
    ).all()
    datasets = [
        EvalDatasetSummary(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            case_count=int(case_count),
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )
        for dataset, case_count in rows
    ]
    return EvalDatasetList(datasets=datasets, total=len(datasets))


def get_eval_dataset(
    session: Session, dataset_id: str
) -> EvalDatasetDetail | None:
    dataset = session.scalar(
        select(EvalDataset)
        .options(
            selectinload(EvalDataset.case_links).selectinload(
                EvalDatasetCase.eval_case
            )
        )
        .where(EvalDataset.id == dataset_id)
    )
    return _dataset_detail(dataset) if dataset is not None else None


def list_eval_results(
    session: Session,
    *,
    agent_version_id: str | None = None,
    dataset_id: str | None = None,
) -> EvalResultList:
    stmt = select(EvalResult).options(selectinload(EvalResult.agent_run))
    if agent_version_id is not None:
        stmt = stmt.where(EvalResult.agent_version_id == agent_version_id)
    if dataset_id is not None:
        stmt = stmt.where(EvalResult.dataset_id == dataset_id)
    results = session.scalars(
        stmt.order_by(EvalResult.created_at.desc(), EvalResult.id)
    ).all()
    reads = [eval_result_to_read(result) for result in results]
    return EvalResultList(results=reads, total=len(reads))


def _latest_complete_run_id(
    session: Session, *, agent_version_id: str, dataset_id: str, case_count: int
) -> str | None:
    return session.scalar(
        select(EvalResult.eval_run_id)
        .where(
            EvalResult.agent_version_id == agent_version_id,
            EvalResult.dataset_id == dataset_id,
        )
        .group_by(EvalResult.eval_run_id)
        .having(func.count(func.distinct(EvalResult.eval_case_id)) == case_count)
        .order_by(func.max(EvalResult.created_at).desc(), EvalResult.eval_run_id.desc())
        .limit(1)
    )


def compare_eval_versions(
    session: Session,
    *,
    version_a: str,
    version_b: str,
    dataset_id: str,
) -> EvalVersionComparison:
    case_count = int(
        session.scalar(
            select(func.count())
            .select_from(EvalDatasetCase)
            .where(EvalDatasetCase.dataset_id == dataset_id)
        )
        or 0
    )
    if case_count == 0:
        raise LookupError(f"Unknown or empty eval dataset: {dataset_id}")
    run_a_id = _latest_complete_run_id(
        session,
        agent_version_id=version_a,
        dataset_id=dataset_id,
        case_count=case_count,
    )
    run_b_id = _latest_complete_run_id(
        session,
        agent_version_id=version_b,
        dataset_id=dataset_id,
        case_count=case_count,
    )
    if run_a_id is None or run_b_id is None:
        missing = version_a if run_a_id is None else version_b
        raise LookupError(
            f"No complete eval run for version {missing} and dataset {dataset_id}"
        )

    results = session.scalars(
        select(EvalResult)
        .where(EvalResult.eval_run_id.in_([run_a_id, run_b_id]))
        .order_by(EvalResult.eval_case_id)
    ).all()
    a_by_case = {
        result.eval_case_id: result
        for result in results
        if result.eval_run_id == run_a_id
    }
    b_by_case = {
        result.eval_case_id: result
        for result in results
        if result.eval_run_id == run_b_id
    }
    comparisons: list[EvalCaseComparison] = []
    for eval_case_id in sorted(set(a_by_case) & set(b_by_case)):
        result_a = a_by_case[eval_case_id]
        result_b = b_by_case[eval_case_id]
        if result_a.passed and not result_b.passed:
            change = "regression"
        elif not result_a.passed and result_b.passed:
            change = "improvement"
        else:
            change = "unchanged"
        comparisons.append(
            EvalCaseComparison(
                eval_case_id=eval_case_id,
                scenario=result_a.scenario,
                result_a_id=result_a.id,
                result_b_id=result_b.id,
                passed_a=result_a.passed,
                passed_b=result_b.passed,
                change=change,
            )
        )
    pass_rate_a = sum(item.passed_a for item in comparisons) / case_count
    pass_rate_b = sum(item.passed_b for item in comparisons) / case_count
    return EvalVersionComparison(
        version_a=version_a,
        version_b=version_b,
        dataset_id=dataset_id,
        run_a_id=run_a_id,
        run_b_id=run_b_id,
        pass_rate_a=round(pass_rate_a, 4),
        pass_rate_b=round(pass_rate_b, 4),
        pass_rate_delta=round(pass_rate_b - pass_rate_a, 4),
        total_cases=case_count,
        cases=comparisons,
        regressions=[item for item in comparisons if item.change == "regression"],
        improvements=[item for item in comparisons if item.change == "improvement"],
    )
