"""
Structured logging setup using structlog.

Why structlog over standard logging:
  Standard logging produces unstructured text like:
    2024-01-01 12:00:00 INFO protein.py:42 Fetched TP53 from UniProt

  structlog produces structured JSON like:
    {"timestamp": "2024-01-01T12:00:00Z", "level": "info", "event": "uniprot_fetch",
     "gene": "TP53", "request_id": "a1b2c3d4", "duration_ms": 142}

  The difference matters because:
  1. Log aggregators (Datadog, CloudWatch, Grafana Loki) can query JSON fields
  2. request_id ties every log line from one request together
  3. Structured fields make alerting on specific genes/errors trivial

request_id propagation:
  Each incoming HTTP request gets a UUID assigned in the logging middleware.
  This ID is injected into the structlog context at the start of the request
  and appears in every log line produced during that request's lifetime —
  across service calls, DB queries, cache hits, everything.

  This means you can grep logs for a single request_id and see the complete
  trace of what happened, in order. Essential for debugging production issues.

In production: set LOG_FORMAT=json (default) for machine-readable output.
In development: set LOG_FORMAT=console for human-readable colored output.
"""

import logging
import sys
import os
import structlog
from structlog.types import EventDict, WrappedLogger


def _add_service_info(logger: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """Add service-level context to every log line."""
    event_dict["service"] = "protein-intelligence-api"
    event_dict["version"] = "1.0.0"
    return event_dict


def _drop_color_message_key(logger: WrappedLogger, method: str, event_dict: EventDict) -> EventDict:
    """Remove uvicorn's color_message field which clutters JSON logs."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for the application.
    Call once at startup in main.py lifespan.

    LOG_FORMAT env var:
      "json"    (default) — machine-readable, for production/Render
      "console" — human-readable colored output, for local dev
    """
    log_format = os.getenv("LOG_FORMAT", "json")
    log_level = logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO

    shared_processors = [
        structlog.contextvars.merge_contextvars,     # injects request_id and other bound vars
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_service_info,
        _drop_color_message_key,
    ]

    if log_format == "console":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route standard library logging through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    for name in ["uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"]:
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structlog logger. Use instead of logging.getLogger()."""
    return structlog.get_logger(name)
