"""RouteFlow errors — Structured error types and exception handlers.

Error shape follows API_SPEC.md §6:
    {
        "error": {
            "type": "<error_type>",
            "message": "<human-readable message>",
            "request_id": "<request_id>"
        }
    }
"""

from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse

from routeflow.core.logging import request_id_var


class ErrorType(StrEnum):
    """Standard error type identifiers from API_SPEC.md §6."""

    UNAUTHORIZED = "unauthorized"
    VALIDATION_ERROR = "validation_error"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    STREAM_ERROR = "stream_error"
    INTERNAL_ERROR = "internal_error"


# Map error types to HTTP status codes.
ERROR_STATUS_CODES: dict[ErrorType, int] = {
    ErrorType.UNAUTHORIZED: 401,
    ErrorType.VALIDATION_ERROR: 400,
    ErrorType.PROVIDER_ERROR: 502,
    ErrorType.RATE_LIMITED: 429,
    ErrorType.TIMEOUT: 504,
    ErrorType.STREAM_ERROR: 502,
    ErrorType.INTERNAL_ERROR: 500,
}


class RouteFlowError(Exception):
    """Base exception for all RouteFlow errors.

    Carries a structured error type and human-readable message that can be
    converted into the standard API error response shape.
    """

    def __init__(self, error_type: ErrorType, message: str) -> None:
        self.error_type = error_type
        self.message = message
        super().__init__(message)


def error_response(error_type: ErrorType, message: str) -> JSONResponse:
    """Build a structured JSON error response matching API_SPEC.md §6."""
    status_code = ERROR_STATUS_CODES.get(error_type, 500)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": error_type.value,
                "message": message,
                "request_id": request_id_var.get() or "-",
            }
        },
    )


async def routeflow_error_handler(_request: Request, exc: RouteFlowError) -> JSONResponse:
    """FastAPI exception handler for RouteFlowError."""
    return error_response(exc.error_type, exc.message)


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Never leaks internal details to the client (SECURITY.md §11).
    """
    return error_response(
        ErrorType.INTERNAL_ERROR,
        "An unexpected internal error occurred.",
    )
