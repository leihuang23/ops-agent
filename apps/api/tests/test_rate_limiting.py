from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from slowapi.wrappers import LimitGroup

from app.core.limiter import build_limiter, limiter
from app.main import create_app


def test_rate_limit_exceeded_returns_429() -> None:
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
        default_limits=[],
    )
    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> object:
        from fastapi import Response

        return Response(
            content='{"detail":"Rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
        )

    @app.get("/limited")
    @limiter.limit("1/minute")
    def limited(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    assert client.get("/limited").status_code == 200
    response = client.get("/limited")
    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"


def test_app_includes_rate_limit_middleware() -> None:
    app = create_app()
    middleware_classes = {m.cls.__name__ for m in app.user_middleware}
    assert "SlowAPIMiddleware" in middleware_classes


def test_build_limiter_falls_back_to_memory_when_redis_is_unavailable(
    monkeypatch,
) -> None:
    class UnavailableRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        def ping(self) -> None:
            raise OSError("redis unavailable")

    import redis

    monkeypatch.setattr(redis.Redis, "from_url", UnavailableRedis.from_url)

    limiter = build_limiter()

    assert limiter._storage.__class__.__name__ == "MemoryStorage"


def test_real_mutation_route_enforces_rate_limit_with_structured_envelope() -> None:
    """Real decorated mutation routes must enforce limits and return the Phase 2
    structured error envelope (not a bare ``{"detail": ...}`` body) on 429.

    The approve route's limit is temporarily lowered to 2/minute so the test
    can exhaust it without making 1000 requests.
    """
    import app.approvals.router  # noqa: F401 — ensure decorators are registered

    route_name = "app.approvals.router.approve"
    original_limits = limiter._route_limits.get(route_name, [])
    original_storage = limiter._storage

    # Build a low limit that uses the same key_func as the original.
    ref = original_limits[0]
    test_limits = list(
        LimitGroup(
            "2/minute",
            ref.key_func,
            ref.scope,
            ref.per_method,
            ref.methods,
            ref.error_message,
            ref.exempt_when,
            ref.cost,
            ref.override_defaults,
        )
    )
    fresh_storage = MemoryStorage("memory://")
    limiter._route_limits[route_name] = test_limits
    limiter._storage = fresh_storage

    try:
        client = TestClient(create_app())
        payload = {"notes": "test"}
        # First two requests go through the handler (may 404 — that's fine,
        # the rate limiter counts the request regardless of response status).
        client.post("/approvals/nonexistent/approve", json=payload)
        client.post("/approvals/nonexistent/approve", json=payload)
        # Third request must be blocked by the rate limiter.
        response = client.post("/approvals/nonexistent/approve", json=payload)

        assert response.status_code == 429
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "rate_limited"
        assert "Rate limit" in body["error"]["message"]
        assert body["error"]["request_id"]
    finally:
        limiter._route_limits[route_name] = original_limits
        limiter._storage = original_storage
        fresh_storage.reset()
