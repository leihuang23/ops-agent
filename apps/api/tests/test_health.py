from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_service_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ops-agent-api",
        "version": "0.1.0",
    }


def test_ready_returns_200_with_dependency_status_when_healthy() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "ok"
    assert body["redis"] == "ok"


def test_ready_returns_503_when_database_is_unreachable(monkeypatch) -> None:
    """A DB failure must surface as 503 with the unhealthy check visible, not a bare 500."""

    def _raising_connect(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("app.health.router.engine.connect", _raising_connect)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert "connection refused" in body["postgres"]
    # Redis is independent — it should still be checked and reported as ok.
    assert body["redis"] == "ok"


def test_ready_returns_503_when_redis_is_unreachable(monkeypatch) -> None:
    """A Redis failure must surface as 503 with the unhealthy check visible, not a bare 500."""

    class UnreachableRedis:
        @classmethod
        def from_url(cls, *_args, **_kwargs):
            return cls()

        def ping(self) -> None:
            raise OSError("redis unavailable")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", UnreachableRedis.from_url)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["postgres"] == "ok"
    assert "redis unavailable" in body["redis"]


def test_ready_returns_503_when_both_dependencies_are_down(monkeypatch) -> None:
    """When both DB and Redis are down, both checks must report their failure."""

    def _raising_connect(*_args, **_kwargs):
        raise OSError("db connection refused")

    class UnreachableRedis:
        @classmethod
        def from_url(cls, *_args, **_kwargs):
            return cls()

        def ping(self) -> None:
            raise OSError("redis unavailable")

    import redis

    monkeypatch.setattr("app.health.router.engine.connect", _raising_connect)
    monkeypatch.setattr(redis.Redis, "from_url", UnreachableRedis.from_url)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert "db connection refused" in body["postgres"]
    assert "redis unavailable" in body["redis"]

