"""RouteFlow runtime retry — Identifies retryable failure exceptions.

Follows ARCHITECTURE.md §8 and retry rules.
- Retries should only happen for temporary failures (rate limits, timeouts, upstream issues).
- Retries must be skipped for auth or validation errors.
"""

from __future__ import annotations

from routeflow.core.errors import RouteFlowError, ErrorType


def is_retryable_error(exc: Exception) -> bool:
    """Evaluate if an exception is temporary and eligible for routing retry."""
    if isinstance(exc, RouteFlowError):
        # Retry for rate limits, timeouts, or upstream network failures
        return exc.error_type in (
            ErrorType.RATE_LIMITED,
            ErrorType.TIMEOUT,
            ErrorType.PROVIDER_ERROR,
        )

    # For any unexpected non-RouteFlowError exception, assume it is not retryable
    # to avoid retry storms on local coding errors.
    return False
