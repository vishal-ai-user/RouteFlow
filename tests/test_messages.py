"""Tests for AEGIS gateway message endpoints.

Verifies:
- POST /v1/messages validates request payloads (API_SPEC.md §4.5)
- POST /v1/messages requires authentication
- POST /v1/messages/count_tokens works (API_SPEC.md §4.4)
- GET /v1/models returns model list (API_SPEC.md §4.3)
- Validation errors match structured error shape (API_SPEC.md §6)
"""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# POST /v1/messages — Authentication
# ---------------------------------------------------------------------------


async def test_messages_requires_auth(client: AsyncClient) -> None:
    """POST /v1/messages without auth should return 401."""
    response = await client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /v1/messages — Validation success
# ---------------------------------------------------------------------------


async def test_messages_valid_request_accepted(auth_client: AsyncClient) -> None:
    """A valid request should pass validation (returns 502 since pipeline not ready)."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        },
    )
    # 502 = provider_error because the pipeline isn't wired yet.
    # This proves auth + validation passed successfully.
    assert response.status_code == 502
    data = response.json()
    assert data["error"]["type"] == "provider_error"


async def test_messages_valid_with_system_prompt(auth_client: AsyncClient) -> None:
    """Request with system prompt should pass validation."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 200,
            "system": "You are a helpful assistant.",
        },
    )
    assert response.status_code == 502


async def test_messages_valid_with_stream_flag(auth_client: AsyncClient) -> None:
    """Request with stream=true should pass validation."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    sse_text = response.text
    assert "message_start" in sse_text
    assert "error" in sse_text
    assert "provider_error" in sse_text


async def test_messages_valid_with_tools(auth_client: AsyncClient) -> None:
    """Request with tool definitions should pass validation."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "What's the weather?"}],
            "max_tokens": 100,
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "input_schema": {"type": "object", "properties": {}},
                }
            ],
        },
    )
    assert response.status_code == 502


async def test_messages_valid_with_thinking(auth_client: AsyncClient) -> None:
    """Request with thinking config should pass validation."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Think about this"}],
            "max_tokens": 1000,
            "thinking": {"type": "enabled", "budget_tokens": 500},
        },
    )
    assert response.status_code == 502


async def test_messages_valid_with_content_blocks(auth_client: AsyncClient) -> None:
    """Request with content block list should pass validation."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Hello world"},
                    ],
                }
            ],
            "max_tokens": 100,
        },
    )
    assert response.status_code == 502


# ---------------------------------------------------------------------------
# POST /v1/messages — Validation failures
# ---------------------------------------------------------------------------


async def test_messages_missing_model_returns_422(auth_client: AsyncClient) -> None:
    """Missing required 'model' field should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        },
    )
    assert response.status_code == 422


async def test_messages_missing_messages_returns_422(auth_client: AsyncClient) -> None:
    """Missing required 'messages' field should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 100,
        },
    )
    assert response.status_code == 422


async def test_messages_empty_messages_returns_422(auth_client: AsyncClient) -> None:
    """Empty messages array should return 422 (min_length=1)."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [],
            "max_tokens": 100,
        },
    )
    assert response.status_code == 422


async def test_messages_missing_max_tokens_returns_422(auth_client: AsyncClient) -> None:
    """Missing required 'max_tokens' field should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 422


async def test_messages_zero_max_tokens_returns_422(auth_client: AsyncClient) -> None:
    """max_tokens=0 should return 422 (gt=0)."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 0,
        },
    )
    assert response.status_code == 422


async def test_messages_negative_max_tokens_returns_422(auth_client: AsyncClient) -> None:
    """max_tokens=-1 should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": -1,
        },
    )
    assert response.status_code == 422


async def test_messages_invalid_temperature_returns_422(auth_client: AsyncClient) -> None:
    """temperature > 1.0 should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
            "temperature": 2.0,
        },
    )
    assert response.status_code == 422


async def test_messages_invalid_json_returns_422(auth_client: AsyncClient) -> None:
    """Completely invalid JSON body should return 422."""
    response = await auth_client.post(
        "/v1/messages",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


async def test_messages_error_includes_request_id(auth_client: AsyncClient) -> None:
    """Pipeline error should include request_id."""
    response = await auth_client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100,
        },
    )
    data = response.json()
    assert data["error"]["request_id"].startswith("req_")


# ---------------------------------------------------------------------------
# POST /v1/messages/count_tokens
# ---------------------------------------------------------------------------


async def test_count_tokens_requires_auth(client: AsyncClient) -> None:
    """POST /v1/messages/count_tokens without auth should return 401."""
    response = await client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 401


async def test_count_tokens_returns_200(auth_client: AsyncClient) -> None:
    """Valid count_tokens request should return 200."""
    response = await auth_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello world"}],
        },
    )
    assert response.status_code == 200


async def test_count_tokens_response_shape(auth_client: AsyncClient) -> None:
    """count_tokens response must have input_tokens field."""
    response = await auth_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hello world"}],
        },
    )
    data = response.json()
    assert "input_tokens" in data
    assert isinstance(data["input_tokens"], int)
    assert data["input_tokens"] > 0


async def test_count_tokens_with_system_prompt(auth_client: AsyncClient) -> None:
    """count_tokens should include system prompt in count."""
    response_no_sys = await auth_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    response_with_sys = await auth_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
            "messages": [{"role": "user", "content": "Hi"}],
            "system": "You are a very detailed assistant with lots of instructions.",
        },
    )
    # System prompt should increase the token count.
    assert response_with_sys.json()["input_tokens"] > response_no_sys.json()["input_tokens"]


async def test_count_tokens_missing_messages_returns_422(auth_client: AsyncClient) -> None:
    """count_tokens with missing messages should return 422."""
    response = await auth_client.post(
        "/v1/messages/count_tokens",
        json={
            "model": "claude-sonnet-4-20250514",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/models
# ---------------------------------------------------------------------------


async def test_models_requires_auth(client: AsyncClient) -> None:
    """GET /v1/models without auth should return 401."""
    response = await client.get("/v1/models")
    assert response.status_code == 401


async def test_models_returns_200(auth_client: AsyncClient) -> None:
    """GET /v1/models with auth should return 200."""
    response = await auth_client.get("/v1/models")
    assert response.status_code == 200


async def test_models_response_shape(auth_client: AsyncClient) -> None:
    """GET /v1/models must match API_SPEC.md §4.3 shape."""
    response = await auth_client.get("/v1/models")
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 1


async def test_models_entry_shape(auth_client: AsyncClient) -> None:
    """Each model entry should have id and type fields."""
    response = await auth_client.get("/v1/models")
    model = response.json()["data"][0]
    assert "id" in model
    assert model["type"] == "model"


async def test_models_returns_default_model(auth_client: AsyncClient) -> None:
    """Model list should include the configured default model."""
    response = await auth_client.get("/v1/models")
    model_ids = [m["id"] for m in response.json()["data"]]
    assert "claude-sonnet-4-20250514" in model_ids


# ---------------------------------------------------------------------------
# POST /v1/messages — Routing integration (mocked)
# ---------------------------------------------------------------------------


async def test_messages_non_stream_success(auth_client: AsyncClient) -> None:
    """POST /v1/messages non-streaming integration success."""
    from aegis.core.schemas import (
        ContentBlockType,
        InternalResponse,
        InternalResponseBlock,
        InternalUsage,
        StopReason,
    )

    mock_res = InternalResponse(
        id="msg_test_123",
        role="assistant",
        content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Hello direct!")],
        model="claude-sonnet-4-20250514",
        stop_reason=StopReason.END_TURN,
        usage=InternalUsage(input_tokens=10, output_tokens=5),
    )

    with patch("aegis.runtime.router.RuntimeRouter.route", new_callable=AsyncMock) as mock_route:
        mock_route.return_value = mock_res

        response = await auth_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "msg_test_123"
        assert data["content"][0]["text"] == "Hello direct!"


async def test_messages_stream_success(auth_client: AsyncClient) -> None:
    """POST /v1/messages streaming integration success."""
    from aegis.core.schemas import ContentBlockType, InternalResponseBlock

    async def mock_stream(request):
        yield InternalResponseBlock(type=ContentBlockType.TEXT, text="Hello")
        yield InternalResponseBlock(type=ContentBlockType.TEXT, text=" world")

    with patch("aegis.runtime.router.RuntimeRouter.route_stream") as mock_route:
        mock_route.side_effect = mock_stream

        response = await auth_client.post(
            "/v1/messages",
            json={
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
                "stream": True,
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        sse_text = response.text
        assert "message_start" in sse_text
        assert "Hello" in sse_text
        assert " world" in sse_text
        assert "message_stop" in sse_text
