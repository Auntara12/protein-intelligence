"""
Metrics endpoints.

GET /api/v1/metrics
  Returns full Prometheus-format metrics text.
  Compatible with any Prometheus scraper, Grafana, Datadog agent, etc.
  Also readable as plain text — useful for quick manual inspection.

GET /api/v1/metrics/summary
  Returns a JSON summary of the most important metrics.
  Designed for the health dashboard or a quick status check.

Example output from /api/v1/metrics/summary:
  {
    "total_requests": 1247,
    "total_errors": 3,
    "error_rate_pct": 0.2,
    "cache_hits": 891,
    "cache_misses": 209,
    "cache_hit_rate_pct": 81.0,
    "active_requests": 2
  }

Interview talking point:
  "The /metrics endpoint exposes Prometheus-format data. I can show you
  live: the cache hit rate is currently 81%, meaning 81% of UniProt and
  AlphaFold calls are served from Redis without hitting the external API.
  The p95 latency on /mutation is 340ms. The /similar endpoint was 8s
  before I moved ESM2 inference to background jobs — now the API response
  is under 200ms."
"""

from fastapi import APIRouter
from fastapi.responses import Response, JSONResponse
from app.core.metrics import get_metrics_output, get_metrics_summary, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """
    Prometheus-format metrics endpoint.
    Scraped by Prometheus, Grafana, Datadog, or readable directly via curl.

    Example:
        curl https://your-api.onrender.com/api/v1/metrics
    """
    content, content_type = get_metrics_output()
    return Response(content=content, media_type=content_type)


@router.get("/metrics/summary")
async def metrics_summary():
    """
    JSON summary of key application metrics.
    Human-readable alternative to the full Prometheus output.

    Returns:
        total_requests: All HTTP requests since startup
        error_rate_pct: Percentage of requests with status >= 400
        cache_hit_rate_pct: Redis cache effectiveness (higher = better)
        active_requests: Currently in-flight requests
    """
    return JSONResponse(content=get_metrics_summary())
