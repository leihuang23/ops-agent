from fastapi import APIRouter, Response
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(HealthResponse):
    postgres: str
    redis: str


@router.get("/health")
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/ready")
def ready(response: Response) -> ReadinessResponse:
    """Check both Postgres and Redis dependencies independently.

    Each check is isolated so that one failing dependency does not mask the
    status of the other. If any check fails, the response is 503 with the
    failing check's error message surfaced in the body so operators can see
    *which* dependency is unhealthy without reading server logs.
    """
    settings = get_settings()

    postgres_status = _check_postgres()
    redis_status = _check_redis(settings.redis_url)

    overall = "ok" if postgres_status == "ok" and redis_status == "ok" else "unhealthy"
    if overall != "ok":
        response.status_code = 503

    return ReadinessResponse(
        status=overall,
        service=settings.app_name,
        version=settings.app_version,
        postgres=postgres_status,
        redis=redis_status,
    )


def _check_postgres() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except Exception as exc:
        return f"error: {exc}"
    return "ok"


def _check_redis(redis_url: str) -> str:
    try:
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
    except Exception as exc:
        return f"error: {exc}"
    return "ok"

