"""RouteFlow auth guards — FastAPI dependencies for endpoint protection.

Follows ARCHITECTURE.md §6:
- authentication must happen early
- failed auth should stop processing immediately
- auth logic should be reusable by API and control center endpoints

Usage::

    from routeflow.auth.guards import require_auth

    @router.post("/v1/messages", dependencies=[Depends(require_auth)])
    async def messages(...): ...
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from routeflow.auth.tokens import validate_token
from routeflow.core.errors import ErrorType, RouteFlowError

# HTTPBearer extracts the token from "Authorization: Bearer <token>".
# auto_error=False lets us return our own structured error instead of FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)

# Module-level dependency to satisfy ruff B008 (no function calls in defaults).
_bearer_dependency = Depends(_bearer_scheme)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> str:
    if request.url.path.startswith("/v1"):
        auth_header = request.headers.get("authorization") or request.headers.get("x-api-key")
        masked_auth = (
            f"{auth_header[:6]}...{auth_header[-4:]}"
            if auth_header and len(auth_header) > 8
            else "None"
        )
        print(f"AUTH_TRACE: Path={request.url.path}, AuthToken={masked_auth}")

    token = credentials.credentials if credentials else request.headers.get("x-api-key")

    if token is None:
        raise RouteFlowError(
            ErrorType.UNAUTHORIZED,
            "Missing authentication token. "
            "Provide an Authorization: Bearer <token> or x-api-key header.",
        )

    if not validate_token(token):
        raise RouteFlowError(
            ErrorType.UNAUTHORIZED,
            "Invalid authentication token.",
        )

    return token
