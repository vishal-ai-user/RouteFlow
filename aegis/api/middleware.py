"""AEGIS middleware — Request ID generation and context injection.

Follows ARCHITECTURE.md §18 and CODING_STANDARDS.md §7:
- generate a unique request ID for every incoming request
- set it in the context variable for structured logging
- return it in a response header for client-side correlation
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from aegis.core.logging import request_id_var

REQUEST_ID_PREFIX = "req_"
REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique ID to each request.

    The ID is:
    1. Stored in a ContextVar so loggers and error handlers can access it.
    2. Returned in the ``X-Request-ID`` response header.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = f"{REQUEST_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        request_id_var.set(request_id)

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id

        return response
