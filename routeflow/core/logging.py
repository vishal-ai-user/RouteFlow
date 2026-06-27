"""RouteFlow logging — Structured logging configuration.

Follows CODING_STANDARDS.md §7 and SECURITY.md §7:
- structured format with timestamps
- request ID support via context
- no secrets in log output
"""

import logging
import sys
from contextvars import ContextVar

# Context variables for per-request tracing.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
provider_id_var: ContextVar[str | None] = ContextVar("provider_id", default=None)
request_origin_var: ContextVar[str | None] = ContextVar("request_origin", default=None)

LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(request_id)s] %(name)s — %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    """Inject the current request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure the root logger for RouteFlow.

    Args:
        log_level: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Clear any existing handlers to avoid duplicate output on reload.
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    handler.addFilter(RequestIdFilter())

    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for the given module.

    Usage::

        from routeflow.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Server started")
    """
    return logging.getLogger(name)
