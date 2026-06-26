"""AEGIS auth guards — FastAPI dependencies for endpoint protection.

Follows ARCHITECTURE.md §6:
- authentication must happen early
- failed auth should stop processing immediately
- auth logic should be reusable by API and control center endpoints

Usage::

    from aegis.auth.guards import require_auth

    @router.post("/v1/messages", dependencies=[Depends(require_auth)])
    async def messages(...): ...
"""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from aegis.auth.tokens import validate_token
from aegis.core.errors import AegisError, ErrorType

# HTTPBearer extracts the token from "Authorization: Bearer <token>".
# auto_error=False lets us return our own structured error instead of FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)

# Module-level dependency to satisfy ruff B008 (no function calls in defaults).
_bearer_dependency = Depends(_bearer_scheme)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = _bearer_dependency,
) -> str:
    """FastAPI dependency that enforces bearer token authentication.

    Raises:
        AegisError: With UNAUTHORIZED type if the token is missing or invalid.

    Returns:
        The validated token string (available to downstream handlers if needed).
    """
    if credentials is None:
        raise AegisError(
            ErrorType.UNAUTHORIZED,
            "Missing authentication token. Provide an Authorization: Bearer <token> header.",
        )

    if not validate_token(credentials.credentials):
        raise AegisError(
            ErrorType.UNAUTHORIZED,
            "Invalid authentication token.",
        )

    return credentials.credentials
