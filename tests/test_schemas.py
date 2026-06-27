"""Tests for RouteFlow internal schemas.

Verifies:
- All internal model types can be constructed
- Enum values are correct
- Default values and optional fields work
- Serialization produces expected output
"""

from routeflow.core.schemas import (
    ContentBlockType,
    InternalContentBlock,
    InternalMessage,
    InternalRequest,
    InternalRequestMetadata,
    InternalResponse,
    InternalResponseBlock,
    InternalThinkingConfig,
    InternalToolDefinition,
    InternalUsage,
    StopReason,
)

# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestContentBlockType:
    """Verify ContentBlockType enum values."""

    def test_text_value(self) -> None:
        assert ContentBlockType.TEXT == "text"

    def test_image_value(self) -> None:
        assert ContentBlockType.IMAGE == "image"

    def test_tool_use_value(self) -> None:
        assert ContentBlockType.TOOL_USE == "tool_use"

    def test_tool_result_value(self) -> None:
        assert ContentBlockType.TOOL_RESULT == "tool_result"

    def test_thinking_value(self) -> None:
        assert ContentBlockType.THINKING == "thinking"

    def test_all_members_present(self) -> None:
        expected = {"text", "image", "tool_use", "tool_result", "thinking"}
        assert {m.value for m in ContentBlockType} == expected


class TestStopReason:
    """Verify StopReason enum values."""

    def test_end_turn_value(self) -> None:
        assert StopReason.END_TURN == "end_turn"

    def test_max_tokens_value(self) -> None:
        assert StopReason.MAX_TOKENS == "max_tokens"

    def test_stop_sequence_value(self) -> None:
        assert StopReason.STOP_SEQUENCE == "stop_sequence"

    def test_tool_use_value(self) -> None:
        assert StopReason.TOOL_USE == "tool_use"

    def test_all_members_present(self) -> None:
        expected = {"end_turn", "max_tokens", "stop_sequence", "tool_use"}
        assert {m.value for m in StopReason} == expected


# ---------------------------------------------------------------------------
# InternalContentBlock tests
# ---------------------------------------------------------------------------


class TestInternalContentBlock:
    """Verify InternalContentBlock construction and defaults."""

    def test_text_block(self) -> None:
        block = InternalContentBlock(type=ContentBlockType.TEXT, text="hello")
        assert block.type == ContentBlockType.TEXT
        assert block.text == "hello"

    def test_tool_use_block(self) -> None:
        block = InternalContentBlock(
            type=ContentBlockType.TOOL_USE,
            tool_use_id="tu_1",
            tool_name="get_weather",
            tool_input={"city": "London"},
        )
        assert block.type == ContentBlockType.TOOL_USE
        assert block.tool_use_id == "tu_1"
        assert block.tool_name == "get_weather"
        assert block.tool_input == {"city": "London"}

    def test_tool_result_block(self) -> None:
        block = InternalContentBlock(
            type=ContentBlockType.TOOL_RESULT,
            tool_result_id="tu_1",
            tool_result_content="Sunny, 25°C",
        )
        assert block.type == ContentBlockType.TOOL_RESULT
        assert block.tool_result_id == "tu_1"
        assert block.tool_result_content == "Sunny, 25°C"

    def test_image_block(self) -> None:
        block = InternalContentBlock(
            type=ContentBlockType.IMAGE,
            image_source={"type": "base64", "data": "abc123"},
        )
        assert block.type == ContentBlockType.IMAGE
        assert block.image_source["type"] == "base64"

    def test_thinking_block(self) -> None:
        block = InternalContentBlock(
            type=ContentBlockType.THINKING,
            thinking_text="Let me think...",
        )
        assert block.type == ContentBlockType.THINKING
        assert block.thinking_text == "Let me think..."

    def test_defaults_are_none(self) -> None:
        block = InternalContentBlock(type=ContentBlockType.TEXT)
        assert block.text is None
        assert block.tool_use_id is None
        assert block.tool_name is None
        assert block.tool_input is None
        assert block.tool_result_id is None
        assert block.tool_result_content is None
        assert block.image_source is None
        assert block.thinking_text is None


# ---------------------------------------------------------------------------
# InternalMessage tests
# ---------------------------------------------------------------------------


class TestInternalMessage:
    """Verify InternalMessage construction."""

    def test_user_message(self) -> None:
        msg = InternalMessage(
            role="user",
            content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
        )
        assert msg.role == "user"
        assert len(msg.content) == 1
        assert msg.content[0].text == "Hello"

    def test_assistant_message(self) -> None:
        msg = InternalMessage(
            role="assistant",
            content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hi there!")],
        )
        assert msg.role == "assistant"

    def test_multi_block_message(self) -> None:
        msg = InternalMessage(
            role="user",
            content=[
                InternalContentBlock(type=ContentBlockType.TEXT, text="Look at this"),
                InternalContentBlock(
                    type=ContentBlockType.IMAGE,
                    image_source={"type": "url", "url": "https://example.com/img.png"},
                ),
            ],
        )
        assert len(msg.content) == 2


# ---------------------------------------------------------------------------
# InternalToolDefinition tests
# ---------------------------------------------------------------------------


class TestInternalToolDefinition:
    """Verify InternalToolDefinition construction."""

    def test_basic_tool(self) -> None:
        tool = InternalToolDefinition(
            name="get_weather",
            description="Get the weather",
            input_schema={"type": "object", "properties": {"city": {"type": "string"}}},
        )
        assert tool.name == "get_weather"
        assert tool.description == "Get the weather"
        assert "properties" in tool.input_schema

    def test_tool_defaults(self) -> None:
        tool = InternalToolDefinition(name="my_tool")
        assert tool.description is None
        assert tool.input_schema == {}


# ---------------------------------------------------------------------------
# InternalThinkingConfig tests
# ---------------------------------------------------------------------------


class TestInternalThinkingConfig:
    """Verify InternalThinkingConfig construction."""

    def test_enabled_with_budget(self) -> None:
        config = InternalThinkingConfig(enabled=True, budget_tokens=500)
        assert config.enabled is True
        assert config.budget_tokens == 500

    def test_disabled(self) -> None:
        config = InternalThinkingConfig(enabled=False)
        assert config.enabled is False
        assert config.budget_tokens is None

    def test_default_enabled(self) -> None:
        config = InternalThinkingConfig()
        assert config.enabled is True


# ---------------------------------------------------------------------------
# InternalRequest tests
# ---------------------------------------------------------------------------


class TestInternalRequest:
    """Verify InternalRequest construction and defaults."""

    def test_minimal_request(self) -> None:
        req = InternalRequest(
            model="test-model",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
                )
            ],
            max_tokens=100,
        )
        assert req.model == "test-model"
        assert len(req.messages) == 1
        assert req.max_tokens == 100
        assert req.stream is False
        assert req.system == []
        assert req.tools is None
        assert req.tool_choice is None
        assert req.thinking is None
        assert req.temperature is None
        assert req.metadata.request_id == ""

    def test_full_request(self) -> None:
        req = InternalRequest(
            model="test-model",
            messages=[
                InternalMessage(
                    role="user",
                    content=[InternalContentBlock(type=ContentBlockType.TEXT, text="Hello")],
                )
            ],
            system=[InternalContentBlock(type=ContentBlockType.TEXT, text="Be helpful")],
            max_tokens=1000,
            temperature=0.7,
            stream=True,
            tools=[InternalToolDefinition(name="search")],
            tool_choice={"type": "auto"},
            thinking=InternalThinkingConfig(enabled=True, budget_tokens=200),
            metadata=InternalRequestMetadata(request_id="req_abc123"),
        )
        assert req.stream is True
        assert req.temperature == 0.7
        assert len(req.system) == 1
        assert req.tools is not None
        assert len(req.tools) == 1
        assert req.tool_choice == {"type": "auto"}
        assert req.thinking is not None
        assert req.thinking.budget_tokens == 200
        assert req.metadata.request_id == "req_abc123"


# ---------------------------------------------------------------------------
# InternalUsage tests
# ---------------------------------------------------------------------------


class TestInternalUsage:
    """Verify InternalUsage construction."""

    def test_defaults(self) -> None:
        usage = InternalUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0

    def test_with_values(self) -> None:
        usage = InternalUsage(input_tokens=150, output_tokens=300)
        assert usage.input_tokens == 150
        assert usage.output_tokens == 300


# ---------------------------------------------------------------------------
# InternalResponseBlock tests
# ---------------------------------------------------------------------------


class TestInternalResponseBlock:
    """Verify InternalResponseBlock construction."""

    def test_text_response_block(self) -> None:
        block = InternalResponseBlock(type=ContentBlockType.TEXT, text="Hello!")
        assert block.type == ContentBlockType.TEXT
        assert block.text == "Hello!"

    def test_tool_use_response_block(self) -> None:
        block = InternalResponseBlock(
            type=ContentBlockType.TOOL_USE,
            tool_use_id="tu_1",
            tool_name="search",
            tool_input={"query": "test"},
        )
        assert block.type == ContentBlockType.TOOL_USE
        assert block.tool_use_id == "tu_1"
        assert block.tool_name == "search"

    def test_thinking_response_block(self) -> None:
        block = InternalResponseBlock(
            type=ContentBlockType.THINKING,
            thinking_text="Analyzing the problem...",
        )
        assert block.type == ContentBlockType.THINKING
        assert block.thinking_text == "Analyzing the problem..."


# ---------------------------------------------------------------------------
# InternalResponse tests
# ---------------------------------------------------------------------------


class TestInternalResponse:
    """Verify InternalResponse construction and defaults."""

    def test_minimal_response(self) -> None:
        resp = InternalResponse(id="msg_001")
        assert resp.id == "msg_001"
        assert resp.role == "assistant"
        assert resp.content == []
        assert resp.model == ""
        assert resp.stop_reason == StopReason.END_TURN
        assert resp.usage.input_tokens == 0
        assert resp.usage.output_tokens == 0

    def test_full_response(self) -> None:
        resp = InternalResponse(
            id="msg_002",
            role="assistant",
            content=[
                InternalResponseBlock(type=ContentBlockType.TEXT, text="The answer is 42."),
            ],
            model="test-model",
            stop_reason=StopReason.MAX_TOKENS,
            usage=InternalUsage(input_tokens=10, output_tokens=50),
        )
        assert resp.id == "msg_002"
        assert len(resp.content) == 1
        assert resp.content[0].text == "The answer is 42."
        assert resp.model == "test-model"
        assert resp.stop_reason == StopReason.MAX_TOKENS
        assert resp.usage.input_tokens == 10
        assert resp.usage.output_tokens == 50

    def test_response_serialization(self) -> None:
        resp = InternalResponse(
            id="msg_003",
            content=[
                InternalResponseBlock(type=ContentBlockType.TEXT, text="Hi"),
            ],
            model="model-a",
            stop_reason=StopReason.END_TURN,
        )
        data = resp.model_dump()
        assert data["id"] == "msg_003"
        assert data["stop_reason"] == "end_turn"
        assert data["content"][0]["type"] == "text"
