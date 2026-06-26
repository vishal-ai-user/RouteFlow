"""Shared test fixtures for the AEGIS test suite."""

import pytest
from httpx import ASGITransport, AsyncClient

from aegis.config.settings import get_settings
from aegis.main import create_app

# Fixed test auth token used across all tests.
TEST_AUTH_TOKEN = "test-aegis-secret-token"


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    """Create a fresh AEGIS app with a known auth token configured."""
    monkeypatch.setenv("AEGIS_AUTH_TOKEN", TEST_AUTH_TOKEN)
    get_settings.cache_clear()
    yield create_app()
    get_settings.cache_clear()


@pytest.fixture
async def client(app):
    """Async HTTP client bound to the test app, WITHOUT auth headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(app):
    """Async HTTP client bound to the test app, WITH valid auth headers."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": f"Bearer {TEST_AUTH_TOKEN}"}
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=headers
    ) as ac:
        yield ac
