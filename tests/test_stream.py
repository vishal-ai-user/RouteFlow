"""Unit tests for the RouteFlow Server-Sent Events (SSE) streaming engine.

Verifies:
- Event formatting and SSE encoder
- Normalization flow (message_start -> content start/delta/stop -> stops -> stop)
- Text, thinking, and tool_use streaming deltas normalization
- Mid-stream error normalization and propagation safety
- FastAPI StreamingResponse creation and headers configuration
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from routeflow.core.errors import RouteFlowError, ErrorType
from routeflow.core.schemas import ContentBlockType, InternalResponseBlock
from routeflow.stream.encoder import encode_sse_event
from routeflow.stream.normalizer import normalize_stream
from routeflow.stream.sse import sse_streaming_response

# ===========================================================================
# SSE Encoder Tests
# ===========================================================================


class TestSseEncoder:
    """Tests formatting event dictionaries into raw Server-Sent Event strings."""

    def test_encode_message_stop(self) -> None:
        event = {"type": "message_stop"}
        encoded = encode_sse_event(event)
        assert encoded == 'event: message_stop\ndata: {"type": "message_stop"}\n\n'

    def test_encode_text_delta(self) -> None:
        event = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "hello"},
        }
        encoded = encode_sse_event(event)
        lines = encoded.split("\n")
        assert lines[0] == "event: content_block_delta"
        assert lines[1].startswith("data: ")
        data_json = json.loads(lines[1].removeprefix("data: "))
        assert data_json["type"] == "content_block_delta"
        assert data_json["delta"]["text"] == "hello"


# ===========================================================================
# Stream Normalizer Tests
# ===========================================================================


class TestStreamNormalizer:
    """Tests mapping InternalResponseBlock streams to Claude-compatible SSE event streams."""

    @pytest.mark.asyncio
    async def test_text_stream_flow(self) -> None:
        async def mock_blocks() -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text="Hello")
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text=" world")

        events_list = []
        async for event in normalize_stream(mock_blocks(), "msg_1", "claude-sonnet", 10):
            events_list.append(event)

        # Expected event sequence:
        # 1. message_start
        # 2. content_block_start (index 0, type text)
        # 3. content_block_delta (text "Hello")
        # 4. content_block_delta (text " world")
        # 5. content_block_stop (index 0)
        # 6. message_delta (stop_reason end_turn)
        # 7. message_stop

        assert len(events_list) == 7
        assert events_list[0]["type"] == "message_start"
        assert events_list[0]["message"]["id"] == "msg_1"
        assert events_list[0]["message"]["model"] == "claude-sonnet"
        assert events_list[0]["message"]["usage"]["input_tokens"] == 10

        assert events_list[1]["type"] == "content_block_start"
        assert events_list[1]["index"] == 0
        assert events_list[1]["content_block"]["type"] == "text"

        assert events_list[2]["type"] == "content_block_delta"
        assert events_list[2]["index"] == 0
        assert events_list[2]["delta"]["text"] == "Hello"

        assert events_list[3]["type"] == "content_block_delta"
        assert events_list[3]["delta"]["text"] == " world"

        assert events_list[4]["type"] == "content_block_stop"
        assert events_list[4]["index"] == 0

        assert events_list[5]["type"] == "message_delta"
        assert events_list[5]["delta"]["stop_reason"] == "end_turn"

        assert events_list[6]["type"] == "message_stop"

    @pytest.mark.asyncio
    async def test_thinking_stream_flow(self) -> None:
        async def mock_blocks() -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(
                type=ContentBlockType.THINKING, thinking_text="Let me process."
            )
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text="Done.")

        events_list = []
        async for event in normalize_stream(mock_blocks(), "msg_2", "claude-sonnet"):
            events_list.append(event)

        # Expected:
        # 1. message_start
        # 2. content_block_start (index 0, type thinking)
        # 3. content_block_delta (thinking)
        # 4. content_block_stop (index 0)
        # 5. content_block_start (index 1, type text)
        # 6. content_block_delta (text)
        # 7. content_block_stop (index 1)
        # 8. message_delta
        # 9. message_stop

        assert len(events_list) == 9
        assert events_list[1]["content_block"]["type"] == "thinking"
        assert events_list[2]["delta"]["thinking"] == "Let me process."
        assert events_list[3]["type"] == "content_block_stop"
        assert events_list[3]["index"] == 0

        assert events_list[4]["content_block"]["type"] == "text"
        assert events_list[5]["delta"]["text"] == "Done."
        assert events_list[6]["type"] == "content_block_stop"
        assert events_list[6]["index"] == 1

    @pytest.mark.asyncio
    async def test_tool_use_stream_flow(self) -> None:
        async def mock_blocks() -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(
                type=ContentBlockType.TOOL_USE,
                tool_use_id="call_99",
                tool_name="get_weather",
                tool_input={"location": "San Francisco"},
            )

        events_list = []
        async for event in normalize_stream(mock_blocks(), "msg_3", "m"):
            events_list.append(event)

        # Expected:
        # 1. message_start
        # 2. content_block_start (index 0, tool_use)
        # 3. content_block_delta (input_json_delta)
        # 4. content_block_stop (index 0)
        # 5. message_delta (stop_reason tool_use)
        # 6. message_stop

        assert len(events_list) == 6
        assert events_list[1]["content_block"]["type"] == "tool_use"
        assert events_list[1]["content_block"]["id"] == "call_99"
        assert events_list[1]["content_block"]["name"] == "get_weather"

        assert events_list[2]["delta"]["type"] == "input_json_delta"
        tool_args = json.loads(events_list[2]["delta"]["partial_json"])
        assert tool_args["location"] == "San Francisco"

        assert events_list[3]["type"] == "content_block_stop"
        assert events_list[4]["delta"]["stop_reason"] == "tool_use"

    @pytest.mark.asyncio
    async def test_mid_stream_provider_error(self) -> None:
        async def mock_error_blocks() -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text="Ok start.")
            raise RouteFlowError(ErrorType.RATE_LIMITED, "Over rate limit")

        events_list = []
        async for event in normalize_stream(mock_error_blocks(), "msg_err", "m"):
            events_list.append(event)

        # Expected:
        # 1. message_start
        # 2. content_block_start
        # 3. content_block_delta
        # 4. error (rate_limited, "Over rate limit") - no stops/stop events should be appended
        assert len(events_list) == 4
        assert events_list[3]["type"] == "error"
        assert events_list[3]["error"]["type"] == "rate_limited"
        assert events_list[3]["error"]["message"] == "Over rate limit"


# ===========================================================================
# SSE StreamingResponse Integration Tests
# ===========================================================================


class TestSseStreamingResponse:
    """Tests wrapping normalized event generators to FastAPI responses."""

    def test_response_headers_and_type(self) -> None:
        async def mock_blocks() -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text="chunk")

        response = sse_streaming_response(mock_blocks(), "id", "model")

        assert response.media_type == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"
        assert response.headers["X-Accel-Buffering"] == "no"
