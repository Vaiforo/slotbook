import hashlib
import math
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings
from app.core.errors import error_response

# Increment and expiry are one atomic operation shared by every API process.
SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('PEXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('PTTL', KEYS[1])}
"""


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limits = {
            "/api/v1/auth/register": self.settings.register_limit,
            "/api/v1/auth/change-password": self.settings.login_limit,
            "/api/v1/auth/login": self.settings.login_limit,
            "/api/v1/bookings": self.settings.booking_limit,
        }
        path = scope.get("path", "").rstrip("/")
        # One per-IP bucket across all specialist search endpoints.
        if path.startswith("/api/v1/specialists/") and path.endswith("/search"):
            path = "/api/v1/ai-search"
            limits[path] = self.settings.ai_limit
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or path not in limits
            or not self.settings.redis_url
        ):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        # Uvicorn accepts forwarded addresses only from the configured trusted proxy.
        host = request.client.host if request.client else "unknown"
        key = (
            self.settings.rate_prefix + ":" + path + ":" + hashlib.sha256(host.encode()).hexdigest()
        )
        redis: Redis = request.app.state.redis
        try:
            count, ttl = await cast(
                Awaitable[list[int]],
                redis.eval(SCRIPT, 1, key, str(self.settings.rate_window_seconds * 1000)),
            )
        except RedisError:
            response = error_response(request, 503, "rate_limit_unavailable", "Попробуйте позже.")
            response.headers["Retry-After"] = "5"
        else:
            if count <= limits[path]:
                await self.app(scope, receive, send)
                return
            response = error_response(request, 429, "rate_limited", "Слишком много запросов.")
            response.headers["Retry-After"] = str(max(1, math.ceil(ttl / 1000)))
        await response(scope, receive, send)
