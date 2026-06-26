"""Tests for AEGIS authentication layer.

Verifies:
- Missing auth token returns 401 (SECURITY.md §4)
- Invalid auth token returns 401
- Valid auth token allows access
- Auth error responses match structured error shape (API_SPEC.md §6)
- Token validation logic (auth/tokens.py)
- Auth disabled when AEGIS_AUTH_TOKEN is not configured
"""

import pytest
from httpx import AsyncClient

from aegis.auth.tokens import validate_token
from aegis.config.settings import get_settings

# ---------------------------------------------------------------------------
# Token validation unit tests
# ---------------------------------------------------------------------------


class TestValidateToken:
    """Unit tests for aegis.auth.tokens.validate_token."""

    def test_valid_token_matches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEGIS_AUTH_TOKEN", "my-secret")
        get_settings.cache_clear()
        assert validate_token("my-secret") is True
        get_settings.cache_clear()

    def test_invalid_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEGIS_AUTH_TOKEN", "my-secret")
        get_settings.cache_clear()
        assert validate_token("wrong-token") is False
        get_settings.cache_clear()

    def test_empty_token_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AEGIS_AUTH_TOKEN", "my-secret")
        get_settings.cache_clear()
        assert validate_token("") is False
        get_settings.cache_clear()

    def test_auth_disabled_when_no_token_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When AEGIS_AUTH_TOKEN is not set, all tokens should be accepted."""
        monkeypatch.delenv("AEGIS_AUTH_TOKEN", raising=False)
        get_settings.cache_clear()
        assert validate_token("any-token") is True
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Auth guard integration tests (via /status which requires auth)
# ---------------------------------------------------------------------------


async def test_missing_auth_returns_401(client: AsyncClient) -> None:
    """Request without Authorization header should get 401."""
    response = await client.get("/status")
    assert response.status_code == 401


async def test_missing_auth_error_shape(client: AsyncClient) -> None:
    """401 error must match API_SPEC.md §6 structured error shape."""
    response = await client.get("/status")
    data = response.json()
    assert "error" in data
    assert data["error"]["type"] == "unauthorized"
    assert "message" in data["error"]
    assert "request_id" in data["error"]


async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    """Request with wrong bearer token should get 401."""
    response = await client.get(
        "/status", headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


async def test_invalid_token_error_message(client: AsyncClient) -> None:
    """Invalid token error should have a clear message."""
    response = await client.get(
        "/status", headers={"Authorization": "Bearer wrong-token"}
    )
    data = response.json()
    assert data["error"]["type"] == "unauthorized"
    assert "invalid" in data["error"]["message"].lower()


async def test_valid_token_allows_access(auth_client: AsyncClient) -> None:
    """Request with correct bearer token should succeed."""
    response = await auth_client.get("/status")
    assert response.status_code == 200


async def test_malformed_auth_header_returns_401(client: AsyncClient) -> None:
    """Non-Bearer auth scheme should get 401."""
    response = await client.get(
        "/status", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert response.status_code == 401


async def test_auth_error_includes_request_id(client: AsyncClient) -> None:
    """Auth errors should include a request_id for tracing."""
    response = await client.get("/status")
    data = response.json()
    assert data["error"]["request_id"].startswith("req_")
