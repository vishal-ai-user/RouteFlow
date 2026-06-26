"""Unit tests for the AEGIS NVIDIA NIM provider adapter.

Verifies request serialization, response deserialization, error normalization,
mock HTTP integration, streaming chunk handling, and credentials safety.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aegis.core.errors import AegisError, ErrorType
from aegis.core.schemas import (
    ContentBlockType,
    InternalContentBlock,
    InternalMessage,
    InternalRequest,
    InternalToolDefinition,
    StopReason,
)
from aegis.providers.nvidia import NvidiaProvider

# ===========================================================================
# Request Serialization Tests
# ===========================================================================


class TestNvidiaRequestSerialization:
    """Tests for mapping InternalRequest to NVIDIA (OpenAI-style) request dicts."""

    def test_basic_request_serialization(self) -> None:
        provider = NvidiaProvider("test", "api-key-1", "https://api.nvidia.com")
        req = InternalRequest(
            model="claude-sonnet",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
                )
            ],
            max_tokens=100,
            temperature=0.7,
        )
        payload = provider.serialize_request(req)

        assert payload["model"] == "claude-sonnet"
        assert payload["max_tokens"] == 100
        assert payload["temperature"] == 0.7
        assert payload["stream"] is False
        assert len(payload["messages"]) == 1
        assert payload["messages"][0] == {"role": "user", "content": "Hello"}

    def test_model_mapping_resolves(self) -> None:
        mapping = {"claude-sonnet": "nvidia/llama-3.1-70b-instruct"}
        provider = NvidiaProvider("test", "k", "https://api", model_mapping=mapping)
        req = InternalRequest(
            model="claude-sonnet",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hi")],
                )
            ],
            max_tokens=50,
        )
        payload = provider.serialize_request(req)
        assert payload["model"] == "nvidia/llama-3.1-70b-instruct"


    def test_system_prompt_merging(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        req = InternalRequest(
            model="m",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hi")],
                )
            ],
            system=[
                InternalContentBlock(type=ContentBlockType.TEXT, text="You are a system system."),
                InternalContentBlock(type=ContentBlockType.TEXT, text="Be polite."),
            ],
            max_tokens=50,
        )
        payload = provider.serialize_request(req)

        assert len(payload["messages"]) == 2
        assert payload["messages"][0] == {
            "role": "system",
            "content": "You are a system system.\nBe polite.",
        }
        assert payload["messages"][1] == {"role": "user", "content": "Hi"}

    def test_history_assistant_thinking_tags(self) -> None:
        """Assistant message thinking blocks should become <think>...</think> in content."""
        provider = NvidiaProvider("test", "k", "https://api")
        req = InternalRequest(
            model="m",
            messages=[
                InternalMessage(
                    role="assistant",
                    content=[
                        InternalContentBlock(
                            type=ContentBlockType.THINKING,
                            thinking_text="Let me think.",
                        ),
                        InternalContentBlock(
                            type=ContentBlockType.TEXT,
                            text="Here is the result.",
                        ),
                    ],
                )
            ],
            max_tokens=50,
        )
        payload = provider.serialize_request(req)

        assert len(payload["messages"]) == 1
        assert payload["messages"][0] == {
            "role": "assistant",
            "content": "<think>Let me think.</think>\nHere is the result.",
        }

    def test_tool_definition_serialization(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        req = InternalRequest(
            model="m",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="call tool")],
                )
            ],
            max_tokens=50,
            tools=[
                InternalToolDefinition(
                    name="get_weather",
                    description="Get weather details",
                    input_schema={"type": "object", "properties": {"location": {"type": "string"}}},
                )
            ],
        )
        payload = provider.serialize_request(req)

        assert "tools" in payload
        assert len(payload["tools"]) == 1
        assert payload["tools"][0] == {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather details",
                "parameters": {"type": "object", "properties": {"location": {"type": "string"}}},
            },
        }

    def test_tool_choice_serialization(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")

        # Case 1: auto
        req = InternalRequest(
            model="m",
            messages=[],
            max_tokens=50,
            tools=[InternalToolDefinition(name="t", input_schema={})],
            tool_choice={"type": "auto"},
        )
        assert provider.serialize_request(req)["tool_choice"] == "auto"

        # Case 2: any / required
        req.tool_choice = {"type": "any"}
        assert provider.serialize_request(req)["tool_choice"] == "required"

        # Case 3: specific tool
        req.tool_choice = {"type": "tool", "name": "t"}
        assert provider.serialize_request(req)["tool_choice"] == {
            "type": "function",
            "function": {"name": "t"},
        }

    def test_user_message_with_tool_results(self) -> None:
        """User messages containing tool results are split into user/tool message sequences."""
        provider = NvidiaProvider("test", "k", "https://api")
        req = InternalRequest(
            model="m",
            messages=[
                InternalMessage(
                    role="user",
                    content=[
                        InternalContentBlock(
                            type=ContentBlockType.TEXT,
                            text="Here is the output:",
                        ),
                        InternalContentBlock(
                            type=ContentBlockType.TOOL_RESULT,
                            tool_result_id="call_1",
                            tool_result_content="42",
                        ),
                    ],
                )
            ],
            max_tokens=50,
        )
        payload = provider.serialize_request(req)

        # Should generate a "user" message followed by a "tool" message
        assert len(payload["messages"]) == 2
        assert payload["messages"][0] == {"role": "user", "content": "Here is the output:"}
        assert payload["messages"][1] == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "42",
        }

    def test_assistant_message_with_tool_use(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        req = InternalRequest(
            model="m",
            messages=[
                InternalMessage(
                    role="assistant",
                    content=[
                        InternalContentBlock(type=ContentBlockType.TEXT, text="I will search."),
                        InternalContentBlock(
                            type=ContentBlockType.TOOL_USE,
                            tool_use_id="call_2",
                            tool_name="search",
                            tool_input={"q": "aegis"},
                        ),
                    ],
                )
            ],
            max_tokens=50,
        )
        payload = provider.serialize_request(req)

        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "assistant"
        assert payload["messages"][0]["content"] == "I will search."
        assert len(payload["messages"][0]["tool_calls"]) == 1
        assert payload["messages"][0]["tool_calls"][0] == {
            "id": "call_2",
            "type": "function",
            "function": {"name": "search", "arguments": '{"q": "aegis"}'},
        }


# ===========================================================================
# Response Deserialization Tests
# ===========================================================================


class TestNvidiaResponseDeserialization:
    """Tests for mapping NVIDIA (OpenAI-style) responses to InternalResponse."""

    def test_basic_text_deserialization(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        data = {
            "id": "chatcmpl-1",
            "model": "nvidia/llama-3",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello there!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15},
        }
        res = provider.deserialize_response(data)

        assert res.id == "chatcmpl-1"
        assert res.model == "nvidia/llama-3"
        assert res.stop_reason == StopReason.END_TURN
        assert res.usage.input_tokens == 10
        assert res.usage.output_tokens == 15
        assert len(res.content) == 1
        assert res.content[0].type == ContentBlockType.TEXT
        assert res.content[0].text == "Hello there!"

    def test_deepseek_reasoning_deserialization(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        data = {
            "id": "chatcmpl-2",
            "model": "deepseek-r1",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Final answer.",
                        "reasoning_content": "Thinking about math...",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 25},
        }
        res = provider.deserialize_response(data)

        assert len(res.content) == 2
        assert res.content[0].type == ContentBlockType.THINKING
        assert res.content[0].thinking_text == "Thinking about math..."
        assert res.content[1].type == ContentBlockType.TEXT
        assert res.content[1].text == "Final answer."

    def test_think_tag_deserialization(self) -> None:
        """Verify fallback parsing of <think>...</think> tags inside content."""
        provider = NvidiaProvider("test", "k", "https://api")
        data = {
            "id": "chatcmpl-3",
            "model": "r1",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "<think>\nAnalyzing prompt...\n</think>\nHere is your response.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        res = provider.deserialize_response(data)

        assert len(res.content) == 2
        assert res.content[0].type == ContentBlockType.THINKING
        assert res.content[0].thinking_text == "Analyzing prompt..."
        assert res.content[1].type == ContentBlockType.TEXT
        assert res.content[1].text == "Here is your response."

    def test_tool_calls_deserialization(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        data = {
            "id": "chatcmpl-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {"name": "calculator", "arguments": '{"exp": "2+2"}'},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
        }
        res = provider.deserialize_response(data)

        assert res.stop_reason == StopReason.TOOL_USE
        assert len(res.content) == 1
        assert res.content[0].type == ContentBlockType.TOOL_USE
        assert res.content[0].tool_use_id == "call_abc"
        assert res.content[0].tool_name == "calculator"
        assert res.content[0].tool_input == {"exp": "2+2"}

    def test_stop_reason_mappings(self) -> None:
        provider = NvidiaProvider("test", "k", "https://api")
        data = {"choices": [{"message": {"role": "assistant"}, "finish_reason": "length"}]}
        assert provider.deserialize_response(data).stop_reason == StopReason.MAX_TOKENS

        data["choices"][0]["finish_reason"] = "stop_sequence"
        assert provider.deserialize_response(data).stop_reason == StopReason.STOP_SEQUENCE

        data["choices"][0]["finish_reason"] = "tool_calls"
        assert provider.deserialize_response(data).stop_reason == StopReason.TOOL_USE


# ===========================================================================
# Endpoint Resolution & Headers
# ===========================================================================


def test_endpoint_resolution_variants() -> None:
    # No trailing suffix
    provider = NvidiaProvider("test", "key", "https://api.nvidia.com")
    assert provider._build_endpoint_url() == "https://api.nvidia.com/v1/chat/completions"

    # Ends with /v1
    provider = NvidiaProvider("test", "key", "https://api.nvidia.com/v1")
    assert provider._build_endpoint_url() == "https://api.nvidia.com/v1/chat/completions"

    # Ends with /chat/completions
    provider = NvidiaProvider("test", "key", "https://api.nvidia.com/v1/chat/completions")
    assert provider._build_endpoint_url() == "https://api.nvidia.com/v1/chat/completions"


def test_auth_headers() -> None:
    provider = NvidiaProvider("test", "nvapi-12345", "https://api")
    headers = provider.get_headers()
    assert headers["Authorization"] == "Bearer nvapi-12345"
    assert headers["Content-Type"] == "application/json"


# ===========================================================================
# Async HTTP & Exception Mapping (Mocked)
# ===========================================================================


class TestNvidiaProviderHttpCalls:
    """Verification of HTTP client executions and AegisError mappings."""

    @pytest.mark.asyncio
    async def test_complete_api_call_success(self) -> None:
        provider = NvidiaProvider("test-member", "key", "https://api")
        req = InternalRequest(
            model="claude-sonnet",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
                )
            ],
            max_tokens=10,
        )

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "cmpl-success",
            "model": "nvidia/model-sonnet",
            "choices": [{"message": {"role": "assistant", "content": "Hi there!"}}],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            response = await provider.complete(req)

            assert response.id == "cmpl-success"
            assert response.content[0].text == "Hi there!"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_status_unauthorized_mapping(self) -> None:
        provider = NvidiaProvider("test-member", "invalid-key", "https://api")
        req = InternalRequest(model="m", messages=[], max_tokens=10)

        # Mock 401 error response
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API Key"}}
        mock_resp.text = "Unauthorized text"

        exc = httpx.HTTPStatusError("Auth error", request=MagicMock(), response=mock_resp)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = exc

            with pytest.raises(AegisError) as exc_info:
                await provider.complete(req)

            assert exc_info.value.error_type == ErrorType.UNAUTHORIZED
            assert "Invalid API Key" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_http_status_rate_limited_mapping(self) -> None:
        provider = NvidiaProvider("test-member", "key", "https://api")
        req = InternalRequest(model="m", messages=[], max_tokens=10)

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"error": {"message": "Quota Exceeded"}}

        exc = httpx.HTTPStatusError("Quota error", request=MagicMock(), response=mock_resp)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = exc

            with pytest.raises(AegisError) as exc_info:
                await provider.complete(req)

            assert exc_info.value.error_type == ErrorType.RATE_LIMITED
            assert "Quota Exceeded" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_timeout_exception_mapping(self) -> None:
        provider = NvidiaProvider("test-member", "key", "https://api")
        req = InternalRequest(model="m", messages=[], max_tokens=10)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(AegisError) as exc_info:
                await provider.complete(req)

            assert exc_info.value.error_type == ErrorType.TIMEOUT
            assert "timed out" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_credentials_safety_on_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify that provider API keys are never exposed in error text or logs."""
        secret_key = "secret_nvapi_xxxx_yyyy_zzzz"
        provider = NvidiaProvider("test-member", secret_key, "https://api")
        req = InternalRequest(model="m", messages=[], max_tokens=10)

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        # Include API key in response text to simulate worst case
        mock_resp.json.side_effect = Exception("No JSON")
        mock_resp.text = f"Invalid API Key: {secret_key}"

        exc = httpx.HTTPStatusError("Auth error", request=MagicMock(), response=mock_resp)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = exc

            with caplog.at_level(logging.ERROR):
                with pytest.raises(AegisError) as exc_info:
                    await provider.complete(req)

                # Ensure error message exposed to gateway/client doesn't have the key
                assert secret_key not in exc_info.value.message
                assert "secret" not in exc_info.value.message.lower()

                # Ensure logged message does not have the key
                for record in caplog.records:
                    assert secret_key not in record.message

    @pytest.mark.asyncio
    async def test_complete_stream_success(self) -> None:
        provider = NvidiaProvider("test-member", "key", "https://api")
        req = InternalRequest(
            model="claude-sonnet",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
                )
            ],
            max_tokens=10,
        )

        # Mock stream lines
        async def mock_iter_lines() -> AsyncIterator[str]:
            yield (
                'data: {"choices": [{"delta": {"reasoning_content": "Thinking about answer."}}]}'
            )
            yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " world!"}}]}'
            yield (
                'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, '
                '"id": "tc1", "function": {"name": "get_time", '
                '"arguments": "{\\"timezone\\":"}}]}}]}'
            )
            yield (
                'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, '
                '"function": {"arguments": "\\"UTC\\"}"}}]}}]}'
            )
            yield "data: [DONE]"

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.iter_lines = mock_iter_lines

        class MockStreamContext:
            async def __aenter__(self) -> MagicMock:
                return mock_resp

            async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
                pass

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = MockStreamContext()

            blocks = []
            async for block in provider.complete_stream(req):
                blocks.append(block)

            assert len(blocks) == 4
            assert blocks[0].type == ContentBlockType.THINKING
            assert blocks[0].thinking_text == "Thinking about answer."
            assert blocks[1].type == ContentBlockType.TEXT
            assert blocks[1].text == "Hello"
            assert blocks[2].type == ContentBlockType.TEXT
            assert blocks[2].text == " world!"
            assert blocks[3].type == ContentBlockType.TOOL_USE
            assert blocks[3].tool_use_id == "tc1"
            assert blocks[3].tool_name == "get_time"
            assert blocks[3].tool_input == {"timezone": "UTC"}
