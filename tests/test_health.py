"""Tests for AEGIS health endpoints.

Verifies:
- GET /health returns correct liveness shape (API_SPEC.md §4.1) — public
- GET /status returns correct status shape (API_SPEC.md §4.2) — requires auth
"""

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# GET /health (public — no auth required)
# ---------------------------------------------------------------------------


async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /health should return 200 without auth."""
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_response_shape(client: AsyncClient) -> None:
    """GET /health must match API_SPEC.md §4.1 shape."""
    response = await client.get("/health")
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "aegis"
    assert data["version"] == "v1"


async def test_health_has_no_extra_fields(client: AsyncClient) -> None:
    """GET /health should return exactly three fields."""
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"ok", "service", "version"}


async def test_health_returns_request_id_header(client: AsyncClient) -> None:
    """Every response should include an X-Request-ID header."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers
    assert response.headers["x-request-id"].startswith("req_")


# ---------------------------------------------------------------------------
# GET /status (requires auth)
# ---------------------------------------------------------------------------


async def test_status_requires_auth(client: AsyncClient) -> None:
    """GET /status without auth should return 401."""
    response = await client.get("/status")
    assert response.status_code == 401


async def test_status_returns_200_with_auth(auth_client: AsyncClient) -> None:
    """GET /status with valid auth should return 200."""
    response = await auth_client.get("/status")
    assert response.status_code == 200


async def test_status_response_shape(auth_client: AsyncClient) -> None:
    """GET /status must match API_SPEC.md §4.2 shape."""
    response = await auth_client.get("/status")
    data = response.json()
    assert data["ok"] is True
    assert data["service"] == "aegis"
    assert "pool" in data
    assert "runtime" in data


async def test_status_pool_fields(auth_client: AsyncClient) -> None:
    """GET /status pool section should have total, healthy, disabled."""
    response = await auth_client.get("/status")
    pool = response.json()["pool"]
    assert "total" in pool
    assert "healthy" in pool
    assert "disabled" in pool


async def test_status_runtime_fields(auth_client: AsyncClient) -> None:
    """GET /status runtime section should have streaming and scheduler."""
    response = await auth_client.get("/status")
    runtime = response.json()["runtime"]
    assert "streaming" in runtime
    assert "scheduler" in runtime
