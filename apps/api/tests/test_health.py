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
    """A DB failure must surface as 503 with a generic error status, not a bare 500."""

    def _raising_connect(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("app.health.router.engine.connect", _raising_connect)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    # The endpoint must not leak raw exception detail (credentials, hostnames).
    assert body["postgres"] == "error"
    assert "connection refused" not in body["postgres"]
    # Redis is independent — it should still be checked and reported as ok.
    assert body["redis"] == "ok"


def test_ready_returns_503_when_redis_is_unreachable(monkeypatch) -> None:
    """A Redis failure must surface as 503 with a generic error status, not a bare 500."""

    class UnreachableRedis:
        @classmethod
        def from_url(cls, *_args, **_kwargs):
            return cls()

        def ping(self) -> None:
            raise OSError("redis unavailable")

        def close(self) -> None:
            pass

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", UnreachableRedis.from_url)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["postgres"] == "ok"
    # The endpoint must not leak raw exception detail.
    assert body["redis"] == "error"
    assert "redis unavailable" not in body["redis"]


def test_ready_returns_503_when_redis_from_url_fails(monkeypatch) -> None:
    """A Redis.from_url failure must also surface as a generic 503 error."""

    def _failing_from_url(*_args, **_kwargs):
        raise ValueError("invalid redis url")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", _failing_from_url)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["postgres"] == "ok"
    assert body["redis"] == "error"
    # Must not leak the URL parsing error.
    assert "invalid redis url" not in str(body)


def test_ready_returns_503_when_both_dependencies_are_down(monkeypatch) -> None:
    """When both DB and Redis are down, both checks must report a generic error."""

    def _raising_connect(*_args, **_kwargs):
        raise OSError("db connection refused")

    class UnreachableRedis:
        @classmethod
        def from_url(cls, *_args, **_kwargs):
            return cls()

        def ping(self) -> None:
            raise OSError("redis unavailable")

        def close(self) -> None:
            pass

    import redis

    monkeypatch.setattr("app.health.router.engine.connect", _raising_connect)
    monkeypatch.setattr(redis.Redis, "from_url", UnreachableRedis.from_url)

    response = client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["postgres"] == "error"
    assert body["redis"] == "error"

