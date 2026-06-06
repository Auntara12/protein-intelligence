"""
Observability middleware.

Two middlewares in this file:

1. RequestContextMiddleware
   Assigns a unique request_id UUID to every incoming request.
   Binds it into the structlog context so every log line produced
   during the request automatically includes the request_id.
   Also logs request start/end with method, path, status, and duration.

2. MetricsMiddleware
   Increments Prometheus counters and histograms for every request.
   Tracks: request count (by method/endpoint/status), request duration,
   and active request gauge.

Both middlewares are applied in main.py. Order matters:
  RequestContextMiddleware runs first (outermost) so the request_id
  is available to MetricsMiddleware and all route handlers.

Why request_id matters:
  Without it, logs look like:
    {"event": "uniprot_fetch_complete", "gene": "TP53", "duration_ms": 142}
    {"event": "cache_miss", "key": "pip:uniprot:TP53:human"}
    {"event": "db_upsert", "table": "proteins"}

  With request_id, every line ties to the same request:
    {"event": "uniprot_fetch_complete", "gene": "TP53", "request_id": "a1b2c3"}
    {"event": "cache_miss", "key": "pip:uniprot:TP53:human", "request_id": "a1b2c3"}
    {"event": "db_upsert", "table": "proteins", "request_id": "a1b2c3"}

  grep/filter for "a1b2c3" and you get the complete trace for one request.
"""

import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from app.core.metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    ACTIVE_REQUESTS,
)

logger = structlog.get_logger(__name__)

# Paths to skip from access logging (too noisy)
_SILENT_PATHS = {"/api/v1/health", "/api/v1/metrics", "/", "/docs", "/redoc", "/openapi.json"}


def _normalize_path(path: str) -> str:
    """
    Normalize dynamic path segments for metric labels to prevent
    Prometheus cardinality explosion.

    Examples:
      /api/v1/protein/TP53           → /api/v1/protein/{gene}
      /api/v1/mutation/TP53/R175H    → /api/v1/mutation/{gene}/{mutation}
      /api/v1/embed/status/abc123    → /api/v1/embed/status/{job_id}
      /api/v1/align/TP53/BRCA1       → /api/v1/align/{gene1}/{gene2}
    """
    # Map: path_prefix → normalized_result
    # Longer/more-specific prefixes must come first.
    PATTERNS = [
        ("/api/v1/mutation/",           "/api/v1/mutation/{gene}/{mutation}"),
        ("/api/v1/align/",              "/api/v1/align/{gene1}/{gene2}"),
        ("/api/v1/compare/",            "/api/v1/compare/{gene1}/{gene2}"),
        ("/api/v1/embed/status/",       "/api/v1/embed/status/{job_id}"),
        ("/api/v1/protein/",            "/api/v1/protein/{gene}"),
        ("/api/v1/structure/",          "/api/v1/structure/{gene}"),
        ("/api/v1/similar/",            "/api/v1/similar/{gene}"),
        ("/api/v1/embed/",              "/api/v1/embed/{gene}"),
        ("/api/v1/report/",             "/api/v1/report/{gene}"),
    ]

    for prefix, normalized in PATTERNS:
        if path.startswith(prefix):
            return normalized

    return path


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Assigns request_id to every request and logs request lifecycle.
    Adds X-Request-ID header to every response so clients can reference it.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start_time = time.perf_counter()

        # Bind request_id into structlog context for this request's lifetime
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        if request.url.path not in _SILENT_PATHS:
            logger.info(
                "request_started",
                client_ip=request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown"),
            )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "request_failed",
                error=str(exc),
                duration_ms=duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if request.url.path not in _SILENT_PATHS:
            log_fn = logger.warning if response.status_code >= 400 else logger.info
            log_fn(
                "request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        # Propagate request_id to client
        response.headers["X-Request-ID"] = request_id
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Records Prometheus metrics for every HTTP request.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = _normalize_path(request.url.path)
        method = request.method
        start_time = time.perf_counter()

        ACTIVE_REQUESTS.inc()
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            status_code = "500"
            raise
        finally:
            duration = time.perf_counter() - start_time
            ACTIVE_REQUESTS.dec()
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=status_code,
            ).inc()
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path,
            ).observe(duration)

        return response
