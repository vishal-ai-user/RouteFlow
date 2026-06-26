"""AEGIS token validation — Verify gateway authentication tokens.

Follows SECURITY.md §4 and ARCHITECTURE.md §6:
- verify API tokens against the configured AEGIS_AUTH_TOKEN
- separate gateway auth from provider credentials
- never log raw tokens
"""

import secrets

from aegis.config.settings import get_settings
from aegis.core.logging import get_logger

logger = get_logger(__name__)


def validate_token(token: str) -> bool:
    """Check whether the provided token matches the configured auth token.

    Args:
        token: The bearer token extracted from the Authorization header.

    Returns:
        True if the token is valid, False otherwise.
    """
    settings = get_settings()

    if settings.auth_token is None:
        # If no auth token is configured, auth is effectively disabled.
        # Log a warning so operators notice.
        logger.warning("AEGIS_AUTH_TOKEN is not configured — auth is disabled")
        return True

    return secrets.compare_digest(token, settings.auth_token)
