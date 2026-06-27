"""Shared test fixtures for the RouteFlow test suite."""

import pathlib

import pytest
from httpx import ASGITransport, AsyncClient

from routeflow.config.settings import get_settings
from routeflow.main import create_app

# Fixed test auth token used across all tests.
TEST_AUTH_TOKEN = "test-aegis-secret-token"


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path):
    """Create a fresh RouteFlow app with a known auth token configured."""
    test_db = tmp_path / "test_routeflow.db"
    monkeypatch.setenv("ROUTEFLOW_AUTH_TOKEN", TEST_AUTH_TOKEN)
    monkeypatch.setenv("ROUTEFLOW_DATABASE_PATH", str(test_db))
    get_settings.cache_clear()

    # Run database migrations for the test database
    from routeflow.persistence.migrations import run_migrations

    run_migrations(str(test_db))

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
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
