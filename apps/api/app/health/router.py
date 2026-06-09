from fastapi import APIRouter
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
def ready() -> ReadinessResponse:
    settings = get_settings()

    with engine.connect() as connection:
        connection.execute(text("select 1"))

    redis_client = Redis.from_url(settings.redis_url)
    redis_client.ping()

    return ReadinessResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        postgres="ok",
        redis="ok",
    )

