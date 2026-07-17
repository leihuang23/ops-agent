from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.agent.persistence import utcnow_naive
from app.agent.service import mark_run_failed_on_timeout
from app.agents.service import DEFAULT_AGENT_ID, DEFAULT_AGENT_VERSION_ID
from app.db.base import Base
from app.models import AgentRun, EvalCase
from app.seed import reseed_database


@pytest.fixture()
def session_factory(
    tmp_path,
) -> Generator[Callable[[], Session], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'celery_timeout_test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    yield TestingSessionLocal

    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_running_run(
    session: Session, *, run_id: str, incident_id: str
) -> AgentRun:
    now = utcnow_naive()
    run = AgentRun(
        id=run_id,
        incident_id=incident_id,
        agent_id=DEFAULT_AGENT_ID,
        agent_version_id=DEFAULT_AGENT_VERSION_ID,
        status="running",
        trace_id="trace_local",
        trace_url=None,
        trace_provider="local",
        trace_metadata={},
        input_payload={"incident_id": incident_id},
        final_report=None,
        token_estimate=0,
        prompt_tokens=0,
        completion_tokens=0,
        cost_estimate_usd=0.0,
        error=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.commit()
    return run


def test_mark_run_failed_on_timeout_flips_in_flight_run_to_failed(
    session_factory: Callable[[], Session],
) -> None:
    """When the Celery soft time limit fires, the run must be marked failed
    with a specific timeout reason immediately, rather than appearing
    'running' until the orphan reaper eventually catches up."""
    with session_factory() as session:
        reseed_database(session)
        case = session.scalars(select(EvalCase).limit(1)).first()
        run = _make_running_run(
            session, run_id="run_timeout_a", incident_id=case.incident_id
        )

        mark_run_failed_on_timeout(
            session, run.id, reason="soft_time_limit_exceeded"
        )
        session.refresh(run)

    assert run.status == "failed"
    assert run.error == "soft_time_limit_exceeded"
    assert run.completed_at is not None


def test_mark_run_failed_on_timeout_does_not_clobber_terminal_run(
    session_factory: Callable[[], Session],
) -> None:
    """A run that already reached a terminal state (e.g. succeeded just
    before the limit fired) must not be overwritten by the timeout handler."""
    with session_factory() as session:
        reseed_database(session)
        case = session.scalars(select(EvalCase).limit(1)).first()
        run = _make_running_run(
            session, run_id="run_timeout_b", incident_id=case.incident_id
        )
        run.status = "succeeded"
        run.error = None
        session.commit()

        mark_run_failed_on_timeout(
            session, run.id, reason="soft_time_limit_exceeded"
        )
        session.refresh(run)

    assert run.status == "succeeded"
    assert run.error is None


def test_investigate_incident_task_marks_run_failed_on_soft_time_limit(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Celery task wrapper must catch SoftTimeLimitExceeded, mark the
    in-flight run failed with a timeout reason, and re-raise so Celery
    records the task failure. Without this, a soft-killed investigation
    appears 'running' until the orphan reaper eventually catches up."""
    from app.agent.tasks import investigate_incident

    with session_factory() as session:
        reseed_database(session)
        case = session.scalars(select(EvalCase).limit(1)).first()
        _make_running_run(
            session, run_id="run_timeout_task", incident_id=case.incident_id
        )

    def raising_execute(session: Session, run_id: str) -> None:
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr(
        "app.agent.service.execute_investigation_run_with_session",
        raising_execute,
    )
    # The task opens its own session via SessionLocal; point it at the test DB.
    monkeypatch.setattr("app.agent.tasks.SessionLocal", session_factory)

    with pytest.raises(SoftTimeLimitExceeded):
        investigate_incident.run("run_timeout_task")

    with session_factory() as session:
        run = session.get(AgentRun, "run_timeout_task")

    assert run is not None
    assert run.status == "failed"
    assert run.error == "soft_time_limit_exceeded"


def test_investigate_incident_task_reraises_original_timeout_when_cleanup_fails(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If recording the timeout on the run row itself raises (DB unavailable,
    pool exhausted), the task must still re-raise the original
    SoftTimeLimitExceeded -- not the cleanup exception -- so Celery records the
    timeout as the task failure and the run is left for the orphan reaper
    instead of masking the timeout with a DB error."""
    from app.agent.tasks import investigate_incident

    with session_factory() as session:
        reseed_database(session)
        case = session.scalars(select(EvalCase).limit(1)).first()
        _make_running_run(
            session, run_id="run_timeout_cleanup_fails", incident_id=case.incident_id
        )

    def raising_execute(session: Session, run_id: str) -> None:
        raise SoftTimeLimitExceeded()

    def raising_mark_failed(session: Session, run_id: str, *, reason: str) -> None:
        raise RuntimeError("simulated cleanup DB failure")

    monkeypatch.setattr(
        "app.agent.service.execute_investigation_run_with_session",
        raising_execute,
    )
    monkeypatch.setattr(
        "app.agent.service.mark_run_failed_on_timeout",
        raising_mark_failed,
    )
    monkeypatch.setattr("app.agent.tasks.SessionLocal", session_factory)

    # The original SoftTimeLimitExceeded must win over the cleanup RuntimeError.
    with pytest.raises(SoftTimeLimitExceeded):
        investigate_incident.run("run_timeout_cleanup_fails")


def test_eval_suite_task_records_timeout_markers_for_unfinished_cases(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the soft time limit fires mid-suite, the task must persist a
    terminal failure marker for every case that never completed, so the eval
    run reads as 'failed' immediately instead of 'running' until the read-path
    staleness self-heal fires (up to the task limit plus 300s)."""
    from app.evals.runner import build_eval_run_summary
    from app.evals.tasks import run_eval_suite_task

    with session_factory() as session:
        reseed_database(session)

    def raising_suite(session: Session, **kwargs: object) -> None:
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr("app.evals.tasks.run_eval_suite", raising_suite)
    monkeypatch.setattr("app.evals.tasks.SessionLocal", session_factory)

    with pytest.raises(SoftTimeLimitExceeded):
        run_eval_suite_task.run(eval_run_id="evalrun_timeout_full")

    with session_factory() as session:
        summary = build_eval_run_summary(session, "evalrun_timeout_full")

    assert summary is not None
    assert summary.status == "failed"
    assert summary.total_scenarios == 6
    for result in summary.results:
        assert result.passed is False
        assert result.failure_reasons == ["soft_time_limit_exceeded"]


def test_eval_suite_task_timeout_preserves_completed_case_results(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cases that already committed a real result keep it; only the cases
    that never ran receive a timeout marker."""
    from app.evals.runner import build_eval_run_summary, record_eval_suite_timeout
    from app.evals.tasks import run_eval_suite_task

    with session_factory() as session:
        reseed_database(session)
        # Simulate one case finishing before the limit fired by pre-recording
        # timeout markers for all but one case through the helper itself.
        record_eval_suite_timeout(
            session,
            eval_run_id="evalrun_timeout_partial",
            dataset_id=None,
            agent_version_id=None,
            only_scenarios={"usage_drop_after_import_outage"},
        )

    def raising_suite(session: Session, **kwargs: object) -> None:
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr("app.evals.tasks.run_eval_suite", raising_suite)
    monkeypatch.setattr("app.evals.tasks.SessionLocal", session_factory)

    with pytest.raises(SoftTimeLimitExceeded):
        run_eval_suite_task.run(eval_run_id="evalrun_timeout_partial")

    with session_factory() as session:
        summary = build_eval_run_summary(session, "evalrun_timeout_partial")

    assert summary is not None
    assert summary.status == "failed"
    assert summary.total_scenarios == 6
    # The pre-existing row must be untouched: exactly one row per case.
    by_scenario = [result.scenario for result in summary.results]
    assert len(by_scenario) == len(set(by_scenario))


def test_eval_suite_task_reraises_original_timeout_when_marker_write_fails(
    session_factory: Callable[[], Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If writing the timeout markers itself fails (DB unavailable), the
    original SoftTimeLimitExceeded must still propagate so Celery records the
    timeout; the partial run is then left for the read-path self-heal."""
    from app.evals.tasks import run_eval_suite_task

    def raising_suite(session: Session, **kwargs: object) -> None:
        raise SoftTimeLimitExceeded()

    def raising_recorder(session: Session, **kwargs: object) -> None:
        raise RuntimeError("simulated marker DB failure")

    monkeypatch.setattr("app.evals.tasks.run_eval_suite", raising_suite)
    monkeypatch.setattr(
        "app.evals.tasks.record_eval_suite_timeout", raising_recorder
    )
    monkeypatch.setattr("app.evals.tasks.SessionLocal", session_factory)

    with pytest.raises(SoftTimeLimitExceeded):
        run_eval_suite_task.run(eval_run_id="evalrun_timeout_cleanup_fails")
