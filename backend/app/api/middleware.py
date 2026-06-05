"""
Rate limiting middleware using the sliding window log algorithm.

Why sliding window over fixed window:
  Fixed window allows 2x burst at window boundaries. If the limit is
  100 req/min and the window resets at :00, a client can send 100 req
  at :59 and 100 req at :00 — 200 requests in 2 seconds.

  Sliding window fixes this: we track the exact timestamp of each
  request in a Redis sorted set, then count how many timestamps fall
  within the last window_seconds. This is O(log n) per request with
  automatic expiry.

Redis data structure: sorted set
  key:   ratelimit:{client_ip}
  score: unix timestamp (float)
  member: unix timestamp as string (unique per request via uuid suffix)

Algorithm:
  1. Remove all members with score < (now - window_seconds)  [ZREMRANGEBYSCORE]
  2. Count remaining members                                  [ZCARD]
  3. If count >= limit: reject with 429
  4. Add current timestamp                                    [ZADD]
  5. Set key expiry to window_seconds                         [EXPIRE]

This is atomic enough for our use case. For strict atomicity, wrap in
a Lua script (shown in the comment below for interview purposes).
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.cache import get_redis

logger = logging.getLogger(__name__)

# Lua script for atomic sliding window (production-grade, avoids race condition)
# between step 2 (count) and step 4 (add). Load once, execute atomically.
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local unique_id = ARGV[4]

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current requests
local count = redis.call('ZCARD', key)

if count >= limit then
    return {0, count}
end

-- Add this request
redis.call('ZADD', key, now, now .. ':' .. unique_id)
redis.call('EXPIRE', key, window)

return {1, count + 1}
"""

# Exempt paths from rate limiting
EXEMPT_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/api/v1/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP sliding window rate limiter.
    Degrades gracefully: if Redis is unavailable, requests pass through.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        allowed, current_count, retry_after = await self._check_rate_limit(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "detail": f"Too many requests. Limit: {settings.RATE_LIMIT_REQUESTS} per {settings.RATE_LIMIT_WINDOW}s.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                },
            )

        response = await call_next(request)

        # Attach rate limit headers to every response
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, settings.RATE_LIMIT_REQUESTS - current_count)
        )
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time()) + settings.RATE_LIMIT_WINDOW
        )
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP, respecting X-Forwarded-For from proxies."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the leftmost (original client) IP
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(self, client_ip: str) -> tuple[bool, int, int]:
        """
        Returns: (allowed, current_request_count, retry_after_seconds)
        Falls back to (True, 0, 0) if Redis is unavailable.
        """
        redis = await get_redis()
        if not redis:
            return True, 0, 0

        key = f"ratelimit:{client_ip}"
        now = time.time()
        import uuid
        unique_id = uuid.uuid4().hex[:8]

        try:
            # Execute Lua script atomically
            result = await redis.eval(
                SLIDING_WINDOW_LUA,
                1,  # number of keys
                key,
                str(now),
                str(settings.RATE_LIMIT_WINDOW),
                str(settings.RATE_LIMIT_REQUESTS),
                unique_id,
            )
            allowed = bool(result[0])
            count = int(result[1])
            retry_after = settings.RATE_LIMIT_WINDOW if not allowed else 0
            return allowed, count, retry_after

        except Exception as e:
            logger.warning(f"Rate limit Redis error for {client_ip}: {e}")
            return True, 0, 0  # fail open
