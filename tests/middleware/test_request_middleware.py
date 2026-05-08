from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio

import pytest
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.middleware import request_middleware
from app.middleware.request_middleware import RedisRateLimitMiddleware, _redact_redis_url


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers or [],
            "client": ("10.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_redact_redis_url_hides_credentials() -> None:
    assert _redact_redis_url("redis://user:secret@redis.internal:6379/1") == "redis://***@redis.internal:6379/1"
    assert _redact_redis_url("redis://redis.internal:6379/1") == "redis://redis.internal:6379/1"


def test_init_fails_open_when_redis_client_cannot_be_created(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(request_middleware.redis, "from_url", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("no redis")))

    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://user:pass@redis:6379/1")

    assert middleware.redis_client is None


def test_dispatch_skips_rate_limit_in_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")
    middleware.redis_client = AsyncMock()
    call_next = AsyncMock(return_value=Response("ok"))
    monkeypatch.setattr(settings, "ENV", "test")

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    middleware.redis_client.incr.assert_not_called()


def test_dispatch_allows_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")
    middleware.redis_client = None
    call_next = AsyncMock(return_value=Response("ok"))

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    call_next.assert_awaited_once()


def test_dispatch_sets_headers_for_allowed_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), max_requests=3, window=60, redis_uri="redis://redis:6379/1")
    redis_client = AsyncMock()
    redis_client.incr.return_value = 1
    middleware.redis_client = redis_client
    call_next = AsyncMock(return_value=Response("ok"))

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "3"
    assert response.headers["X-RateLimit-Remaining"] == "2"
    redis_client.expire.assert_awaited_once()


def test_dispatch_returns_429_when_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), max_requests=1, window=30, redis_uri="redis://redis:6379/1")
    redis_client = AsyncMock()
    redis_client.incr.return_value = 2
    middleware.redis_client = redis_client
    call_next = AsyncMock(return_value=Response("ok"))

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    call_next.assert_not_awaited()


def test_dispatch_fails_open_for_redis_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ENV", "production")
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")
    redis_client = AsyncMock()
    redis_client.incr.side_effect = RedisError("down")
    middleware.redis_client = redis_client
    call_next = AsyncMock(return_value=Response("ok"))

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    call_next.assert_awaited_once()


def test_dispatch_fails_open_when_error_stringification_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class BadException(Exception):
        def __str__(self) -> str:
            raise RuntimeError("stringify failed")

    monkeypatch.setattr(settings, "ENV", "production")
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")
    redis_client = AsyncMock()
    redis_client.incr.side_effect = BadException()
    middleware.redis_client = redis_client
    call_next = AsyncMock(return_value=Response("ok"))

    response = asyncio.run(middleware.dispatch(_request(), call_next))

    assert response.status_code == 200
    call_next.assert_awaited_once()


def test_client_identifier_prefers_proxy_headers() -> None:
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1", trust_proxy=True)

    assert middleware._get_client_identifier(_request([(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")])) == "203.0.113.10"
    assert middleware._get_client_identifier(_request([(b"x-real-ip", b"203.0.113.11")])) == "203.0.113.11"


def test_client_identifier_handles_missing_client() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")

    assert middleware._get_client_identifier(request) == "unknown"


def test_close_closes_redis_client() -> None:
    middleware = RedisRateLimitMiddleware(app=AsyncMock(), redis_uri="redis://redis:6379/1")
    middleware.redis_client = SimpleNamespace(close=AsyncMock())

    asyncio.run(middleware.close())

    middleware.redis_client.close.assert_awaited_once()
