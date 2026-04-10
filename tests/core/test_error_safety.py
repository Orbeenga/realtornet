import asyncio
from unittest.mock import patch

from fastapi import FastAPI
from fastapi import Request
from starlette.responses import Response

from app.middleware.request_middleware import RedisRateLimitMiddleware
from app.models.agent_profiles import AgentProfile


class BrokenStringError(Exception):
    def __str__(self) -> str:
        raise RuntimeError("stringification failed")


class BrokenRedisClient:
    async def incr(self, key: str) -> int:
        raise BrokenStringError()


def test_agent_profile_repr_uses_loaded_dict_values_only():
    profile = AgentProfile.__new__(AgentProfile)

    assert repr(profile) == (
        "<AgentProfile(profile_id=unknown, user_id=unknown, license=unknown)>"
    )


def test_rate_limit_middleware_handles_unstringifiable_exceptions():
    app = FastAPI()
    middleware = RedisRateLimitMiddleware(app)
    middleware.redis_client = BrokenRedisClient()

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/account/listings",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }
    )

    async def call_next(_: Request) -> Response:
        return Response(content="ok", status_code=200)

    with patch("app.middleware.request_middleware.settings.ENV", "development"):
        with patch("app.middleware.request_middleware.logger.error") as mock_error:
            response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 200
    assert mock_error.call_args.kwargs["extra"]["error"] == "BrokenStringError"
