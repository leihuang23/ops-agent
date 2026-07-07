from __future__ import annotations

from collections.abc import Callable, Generator

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.agent.persistence import utcnow_naive
from app.agent.service import mark_run_failed_on_timeout
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
            session, run.id, reason="celery soft time limit exceeded"
        )
        session.refresh(run)

    assert run.status == "failed"
    assert run.error == "celery soft time limit exceeded"
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
            session, run.id, reason="celery soft time limit exceeded"
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
    assert run.error == "celery soft time limit exceeded"


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
