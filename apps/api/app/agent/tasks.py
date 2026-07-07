from __future__ import annotations

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.logging_config import get_logger

logger = get_logger(__name__)


@celery_app.task
def investigate_incident(run_id: str) -> dict[str, object]:
    """Run an investigation synchronously within a Celery worker.

    Not retryable: a partial run corrupts agent state, so fail-fast is safer
    than a blind retry. The Celery ``task_time_limit`` / ``task_soft_time_limit``
    guard against hangs; if the soft limit fires we mark the run failed
    immediately (with a specific timeout reason) so it does not appear
    "running" while waiting for the orphan reaper, then re-raise so Celery
    records the task failure.
    """
    from app.agent.service import (
        execute_investigation_run_with_session,
        mark_run_failed_on_timeout,
    )

    try:
        with SessionLocal() as session:
            detail = execute_investigation_run_with_session(session, run_id)
    except SoftTimeLimitExceeded:
        # The in-flight session is rolled back when its ``with`` block exits;
        # use a fresh session to record the timeout on the run row. If the
        # cleanup itself raises (DB unavailable, pool exhausted), log it but
        # still re-raise the *original* SoftTimeLimitExceeded so Celery records
        # the timeout as the task failure and monitoring keyed on it still
        # fires. The run row is then left for the orphan reaper to reclaim.
        try:
            with SessionLocal() as session:
                mark_run_failed_on_timeout(
                    session, run_id, reason="celery soft time limit exceeded"
                )
        except Exception:
            logger.exception(
                "Failed to mark agent run failed after soft time limit; "
                "leaving it for the orphan reaper",
                extra={"run_id": run_id},
            )
        raise

    return {
        "run_id": detail.id,
        "status": detail.status,
        "incident_id": detail.incident_id,
    }
