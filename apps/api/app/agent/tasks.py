from __future__ import annotations

from app.celery_app import celery_app
from app.db.session import SessionLocal


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def investigate_incident(self, run_id: str) -> dict[str, object]:
    from app.agent.service import execute_investigation_run_with_session

    with SessionLocal() as session:
        detail = execute_investigation_run_with_session(session, run_id)

    return {
        "run_id": detail.id,
        "status": detail.status,
        "incident_id": detail.incident_id,
    }
