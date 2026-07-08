from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.agent.schemas import AgentInvestigationCreate, AgentRunDetail, AgentRunSummary
from app.agent.service import (
    create_investigation_run,
    get_run_detail,
    list_agent_runs,
    start_investigation_run,
)
from app.agent.tasks import investigate_incident
from app.core.access import require_demo_data_access, require_demo_operator_access
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    dependencies=[Depends(require_demo_data_access)],
)

_settings = get_settings()


def _enqueue_investigation(run_id: str) -> None:
    settings = get_settings()
    if settings.app_env == "test":
        investigate_incident.run(run_id)
    else:
        investigate_incident.delay(run_id)


@router.post("/investigations")
@limiter.limit(f"{_settings.rate_limit_mutations_per_minute}/minute")
def start_investigation(
    request: Request,
    payload: AgentInvestigationCreate,
    response: Response,
    _operator: None = Depends(require_demo_operator_access),
    db: Session = Depends(get_db),
) -> AgentRunDetail:
    try:
        if payload.run_inline:
            run, created = start_investigation_run(
                db,
                payload.incident_id,
                force=payload.force,
                idempotency_key=payload.idempotency_key,
                agent_version_id=payload.agent_version_id,
            )
        else:
            run, created = create_investigation_run(
                db,
                payload.incident_id,
                force=payload.force,
                idempotency_key=payload.idempotency_key,
                agent_version_id=payload.agent_version_id,
            )
            if created:
                _enqueue_investigation(run.id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return run


@router.get("/runs")
def agent_runs(db: Session = Depends(get_db)) -> list[AgentRunSummary]:
    return list_agent_runs(db)


@router.get("/runs/{run_id}")
def agent_run_detail(run_id: str, db: Session = Depends(get_db)) -> AgentRunDetail:
    try:
        return get_run_detail(db, run_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
