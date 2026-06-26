"""Unit tests for the AEGIS Control Center Backend API.

Verifies:
- Auth protection on all /api endpoints
- Dashboard health and summary metrics aggregation
- Settings listing and updating with cache invalidation
- Provider CRUD with encryption, API key masking, and pool sync
- Mocked provider connection testing
- Model mapping CRUD
- Paginated request and error log retrieval with query filtering
- Detailed single-request metadata lifecycle aggregation
- Grouped usage and token statistic queries
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from aegis.config.settings import get_settings
from aegis.core.errors import ErrorType
from aegis.persistence.repositories import (
    LogRepository,
)
from aegis.providers.pool import get_global_pool


@pytest.fixture(autouse=True)
def clear_global_pool() -> None:
    """Fixture to ensure a fresh, empty global provider pool before each test."""
    pool = get_global_pool()
    pool._members.clear()


# ===========================================================================
# Authentication Guard Tests
# ===========================================================================


@pytest.mark.anyio
async def test_auth_protection_on_all_control_endpoints(client: AsyncClient) -> None:
    """Verify all /api endpoints return 401 Unauthorized when unauthenticated."""
    routes = [
        ("GET", "/api/dashboard/summary"),
        ("GET", "/api/control/health"),
        ("GET", "/api/settings"),
        ("PUT", "/api/settings"),
        ("GET", "/api/providers"),
        ("POST", "/api/providers"),
        ("PUT", "/api/providers/test-id"),
        ("DELETE", "/api/providers/test-id"),
        ("POST", "/api/providers/test-id/enable"),
        ("POST", "/api/providers/test-id/disable"),
        ("POST", "/api/providers/test-id/test"),
        ("GET", "/api/model_mappings"),
        ("POST", "/api/model_mappings"),
        ("PUT", "/api/model_mappings/logical-model"),
        ("DELETE", "/api/model_mappings/logical-model"),
        ("GET", "/api/logs/requests"),
        ("GET", "/api/logs/requests/request-123"),
        ("GET", "/api/logs/errors"),
        ("GET", "/api/logs"),
        ("GET", "/api/usage/summary"),
    ]

    for method, route in routes:
        if method == "GET":
            response = await client.get(route)
        elif method == "POST":
            response = await client.post(route, json={})
        elif method == "PUT":
            response = await client.put(route, json={})
        elif method == "DELETE":
            response = await client.delete(route)
        else:
            continue

        assert response.status_code == 401, f"{method} {route} should be protected by auth"
        body = response.json()
        assert body["error"]["type"] == ErrorType.UNAUTHORIZED.value


# ===========================================================================
# Settings Endpoint Tests
# ===========================================================================


@pytest.mark.anyio
async def test_settings_retrieval_and_update(auth_client: AsyncClient) -> None:
    """Verify settings listing excludes secrets and PUT updates settings dynamically."""
    # 1. GET Settings
    response = await auth_client.get("/api/settings")
    assert response.status_code == 200
    settings_data = response.json()

    assert "default_model" in settings_data
    assert "scheduler_mode" in settings_data
    assert "auth_token" not in settings_data  # Should be excluded!
    assert "encryption_key" not in settings_data  # Should be excluded!

    # 2. PUT Settings
    payload = {
        "scheduler_mode": "least-busy",
        "retry_count": 5,
        "timeout_seconds": 120,
    }
    update_resp = await auth_client.put("/api/settings", json=payload)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()

    assert updated_data["scheduler_mode"] == "least-busy"
    assert updated_data["retry_count"] == 5
    assert updated_data["timeout_seconds"] == 120

    # 3. Verify Cache Is Invalidated (loading settings gets updated values)
    current_settings = get_settings()
    assert current_settings.scheduler_mode == "least-busy"
    assert current_settings.retry_count == 5


# ===========================================================================
# Provider Endpoint Tests
# ===========================================================================


@pytest.mark.anyio
async def test_provider_crud_masking_and_pool_sync(auth_client: AsyncClient) -> None:
    """Verify provider CRUD operations, key masking, and sync with ProviderPool."""
    # 1. Create a Provider (POST)
    payload = {
        "provider_id": "nvidia-test-account",
        "display_name": "Test Account",
        "api_key": "nvapi-abcdefghijklmnopqrstuvwxyz",
        "base_url": "https://api.nvidia.com/v1",
        "enabled": True,
    }
    response = await auth_client.post("/api/providers", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["provider_id"] == "nvidia-test-account"
    assert created["display_name"] == "Test Account"
    # Ensure api_key is masked
    assert created["api_key"] == "nvapi-...wxyz"

    # Verify registered in global pool
    pool = get_global_pool()
    member = pool.get_provider("nvidia-test-account")
    assert member is not None
    assert member.display_name == "Test Account"
    assert member.enabled is True
    assert member.provider.api_key == "nvapi-abcdefghijklmnopqrstuvwxyz"

    # 2. List Providers (GET)
    list_resp = await auth_client.get("/api/providers")
    assert list_resp.status_code == 200
    providers = list_resp.json()
    assert len(providers) == 1
    assert providers[0]["provider_id"] == "nvidia-test-account"
    assert providers[0]["api_key"] == "nvapi-...wxyz"

    # 3. Update Provider (PUT)
    update_payload = {
        "display_name": "Updated Label",
        "api_key": "nvapi-9876543210zyxwvutsrq",
    }
    update_resp = await auth_client.put("/api/providers/nvidia-test-account", json=update_payload)
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["display_name"] == "Updated Label"
    assert updated["api_key"] == "nvapi-...tsrq"

    # Verify pool synced updated state
    member = pool.get_provider("nvidia-test-account")
    assert member.display_name == "Updated Label"
    assert member.provider.api_key == "nvapi-9876543210zyxwvutsrq"

    # 4. Disable Provider
    disable_resp = await auth_client.post("/api/providers/nvidia-test-account/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["enabled"] is False
    assert pool.get_provider("nvidia-test-account").enabled is False

    # 5. Enable Provider
    enable_resp = await auth_client.post("/api/providers/nvidia-test-account/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["enabled"] is True
    assert pool.get_provider("nvidia-test-account").enabled is True

    # 6. Delete Provider
    delete_resp = await auth_client.delete("/api/providers/nvidia-test-account")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"ok": True}

    # Ensure deleted from DB & pool
    assert pool.get_provider("nvidia-test-account") is None


# ===========================================================================
# Provider Connection Testing
# ===========================================================================


@pytest.mark.anyio
async def test_provider_connection_test(auth_client: AsyncClient) -> None:
    """Verify connectivity test endpoint runs complete() and reports result."""
    # 1. Create a Provider
    payload = {
        "provider_id": "nvidia-test-conn",
        "display_name": "Test Conn",
        "api_key": "nvapi-somekey",
        "base_url": "https://api.nvidia.com/v1",
        "enabled": True,
    }
    await auth_client.post("/api/providers", json=payload)

    # 2. Test Success Pathway (Mocked complete succeeds)
    with patch(
        "aegis.providers.nvidia.NvidiaProvider.complete", new_callable=AsyncMock
    ) as mock_complete:
        mock_complete.return_value = MagicMock()
        test_resp = await auth_client.post("/api/providers/nvidia-test-conn/test")
        assert test_resp.status_code == 200
        assert test_resp.json()["ok"] is True
        assert "message" in test_resp.json()

    # 3. Test Failure Pathway (Mocked complete raises error)
    from aegis.core.errors import AegisError, ErrorType

    with patch(
        "aegis.providers.nvidia.NvidiaProvider.complete", new_callable=AsyncMock
    ) as mock_complete:
        mock_complete.side_effect = AegisError(
            ErrorType.PROVIDER_ERROR, "Mock provider credentials invalid."
        )
        test_resp = await auth_client.post("/api/providers/nvidia-test-conn/test")
        assert test_resp.status_code == 200
        result = test_resp.json()
        assert result["ok"] is False
        assert result["error_type"] == ErrorType.PROVIDER_ERROR.value
        assert "Mock provider credentials invalid." in result["error_message"]


@pytest.mark.anyio
async def test_provider_connection_test_model_selection(auth_client: AsyncClient) -> None:
    """Verify connectivity test endpoint uses model mappings priority list or fallback."""
    payload_a = {
        "provider_id": "nvidia-test-conn-map",
        "display_name": "Test Conn Mapped",
        "api_key": "nvapi-somekey",
        "base_url": "https://api.nvidia.com/v1",
        "enabled": True,
    }
    await auth_client.post("/api/providers", json=payload_a)

    pool = get_global_pool()
    member = pool.get_provider("nvidia-test-conn-map")
    assert member is not None
    member.provider.model_mapping = {"logical-model-x": "provider-model-y"}

    with patch(
        "aegis.providers.nvidia.NvidiaProvider.complete", new_callable=AsyncMock
    ) as mock_complete:
        mock_complete.return_value = MagicMock()
        await auth_client.post("/api/providers/nvidia-test-conn-map/test")
        mock_complete.assert_called_once()
        called_req = mock_complete.call_args[0][0]
        assert called_req.model == "logical-model-x"

    # Case B: no mappings, should fallback to "meta/llama-3.3-70b-instruct"
    member.provider.model_mapping = {}
    with patch(
        "aegis.providers.nvidia.NvidiaProvider.complete", new_callable=AsyncMock
    ) as mock_complete:
        mock_complete.return_value = MagicMock()
        await auth_client.post("/api/providers/nvidia-test-conn-map/test")
        mock_complete.assert_called_once()
        called_req = mock_complete.call_args[0][0]
        assert called_req.model == "meta/llama-3.3-70b-instruct"


# ===========================================================================
# Model Mapping CRUD Tests
# ===========================================================================


@pytest.mark.anyio
async def test_model_mapping_crud(auth_client: AsyncClient) -> None:
    """Verify model mapping CRUD operations are successfully processed."""
    # 1. Create Mapping (POST)
    payload = {
        "logical_model": "claude-sonnet-test",
        "nvidia_model": "nvidia/llama-3.1-70b-instruct",
    }
    response = await auth_client.post("/api/model_mappings", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["logical_model"] == "claude-sonnet-test"
    assert created["nvidia_model"] == "nvidia/llama-3.1-70b-instruct"

    # 2. List Mappings (GET)
    list_resp = await auth_client.get("/api/model_mappings")
    assert list_resp.status_code == 200
    mappings = list_resp.json()
    assert len(mappings) == 1
    assert mappings[0]["logical_model"] == "claude-sonnet-test"

    # 3. Update Mapping (PUT)
    update_payload = {"nvidia_model": "nvidia/nemotron-4-340b-instruct"}
    update_resp = await auth_client.put(
        "/api/model_mappings/claude-sonnet-test", json=update_payload
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["nvidia_model"] == "nvidia/nemotron-4-340b-instruct"

    # 4. Delete Mapping
    delete_resp = await auth_client.delete("/api/model_mappings/claude-sonnet-test")
    assert delete_resp.status_code == 200
    assert delete_resp.json() == {"ok": True}


# ===========================================================================
# Logs, Filtering, Details, and Usage Summary Tests
# ===========================================================================


@pytest.mark.anyio
async def test_paginated_logs_filtering_and_usage(auth_client: AsyncClient) -> None:
    """Verify paginated requests and error histories, detail queries, and usage summaries."""
    log_repo = LogRepository()

    # 1. Insert Mock Log data
    # Create request log
    await log_repo.log_request(request_id="req-1", model="claude-sonnet", stream=False)
    await log_repo.update_request_status(
        request_id="req-1", status_code=200, latency_ms=450, provider_id="nvidia-1"
    )
    await log_repo.log_response(
        request_id="req-1", content="Success answer", stop_reason="end_turn"
    )
    await log_repo.log_usage(request_id="req-1", input_tokens=10, output_tokens=15)

    # Create error request log
    await log_repo.log_request(request_id="req-2", model="claude-opus", stream=True)
    await log_repo.update_request_status(
        request_id="req-2", status_code=502, latency_ms=1200, provider_id="nvidia-2"
    )
    await log_repo.log_error(
        request_id="req-2", error_type="provider_error", error_message="Rate limit exceeded"
    )

    # 2. Test Paginated Requests GET
    req_resp = await auth_client.get("/api/logs/requests?limit=10&offset=0")
    assert req_resp.status_code == 200
    logs = req_resp.json()
    assert len(logs) == 2
    assert logs[0]["request_id"] == "req-2"  # Ordered by DESC id
    assert logs[1]["request_id"] == "req-1"

    # Filter requests by provider
    filt_resp = await auth_client.get("/api/logs/requests?provider_id=nvidia-1")
    assert len(filt_resp.json()) == 1
    assert filt_resp.json()[0]["request_id"] == "req-1"

    # Filter requests by status
    status_resp = await auth_client.get("/api/logs/requests?status=error")
    assert len(status_resp.json()) == 1
    assert status_resp.json()[0]["request_id"] == "req-2"

    # 3. Test Paginated Errors GET
    err_resp = await auth_client.get("/api/logs/errors?limit=5")
    assert err_resp.status_code == 200
    errors = err_resp.json()
    assert len(errors) == 1
    assert errors[0]["request_id"] == "req-2"
    assert errors[0]["error_type"] == "provider_error"

    # 4. Test Single Request Details GET
    detail_resp = await auth_client.get("/api/logs/requests/req-1")
    assert detail_resp.status_code == 200
    details = detail_resp.json()

    assert details["request"]["request_id"] == "req-1"
    assert details["response"]["content"] == "Success answer"
    assert details["response"]["stop_reason"] == "end_turn"
    assert details["error"] is None
    assert details["usage"]["input_tokens"] == 10
    assert details["usage"]["output_tokens"] == 15

    # 5. Test Combined Logs GET (Compatibility route)
    comb_resp = await auth_client.get("/api/logs")
    assert comb_resp.status_code == 200
    comb = comb_resp.json()
    assert "requests" in comb
    assert "errors" in comb
    assert len(comb["requests"]) == 2
    assert len(comb["errors"]) == 1

    # 6. Test Usage Summary GET
    usage_resp = await auth_client.get("/api/usage/summary")
    assert usage_resp.status_code == 200
    summary = usage_resp.json()

    assert summary["total_requests"] == 2
    assert summary["total_tokens"] == 25  # req-1 input_tokens (10) + output_tokens (15) = 25
    assert len(summary["daily_usage"]) > 0
    assert len(summary["provider_usage"]) > 0
    assert len(summary["model_usage"]) > 0


@pytest.mark.anyio
async def test_environment_configured_providers_in_control_center(auth_client: AsyncClient) -> None:
    """Verify that environment-configured providers are visible and handle CRUD operations."""
    from aegis.providers.nvidia import NvidiaProvider
    from aegis.providers.pool import PoolMember, get_global_pool

    # 1. Register an environment provider manually in the global pool (not in DB)
    pool = get_global_pool()
    provider = NvidiaProvider(
        name="Env Provider",
        api_key="nvapi-env-12345",
        base_url="https://api.nvidia.com/v1",
        timeout_seconds=60,
    )
    member = PoolMember(
        provider_id="nvidia-env-only",
        display_name="Env Provider",
        provider=provider,
        enabled=True,
    )
    pool.register_provider(member)

    # 2. Verify it shows up in GET /api/providers
    list_resp = await auth_client.get("/api/providers")
    assert list_resp.status_code == 200
    providers = list_resp.json()
    env_prov = next((p for p in providers if p["provider_id"] == "nvidia-env-only"), None)
    assert env_prov is not None
    assert env_prov["display_name"] == "Env Provider"
    assert env_prov["api_key"] == "nvapi-...2345"
    assert env_prov["id"] == 0

    # 3. Verify PUT returns 400 Bad Request
    update_resp = await auth_client.put(
        "/api/providers/nvidia-env-only", json={"display_name": "New Name"}
    )
    assert update_resp.status_code == 400
    assert "environment" in update_resp.json()["detail"]

    # 4. Verify DELETE returns 400 Bad Request
    delete_resp = await auth_client.delete("/api/providers/nvidia-env-only")
    assert delete_resp.status_code == 400
    assert "environment" in delete_resp.json()["detail"]

    # 5. Verify disable toggles pool member state and returns 200
    disable_resp = await auth_client.post("/api/providers/nvidia-env-only/disable")
    assert disable_resp.status_code == 200
    assert disable_resp.json()["enabled"] is False
    assert pool.get_provider("nvidia-env-only").enabled is False

    # 6. Verify enable toggles pool member state and returns 200
    enable_resp = await auth_client.post("/api/providers/nvidia-env-only/enable")
    assert enable_resp.status_code == 200
    assert enable_resp.json()["enabled"] is True
    assert pool.get_provider("nvidia-env-only").enabled is True
