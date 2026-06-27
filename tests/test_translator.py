"""Tests for RouteFlow translator layer.

Verifies:
- Request translation: Claude-compatible → InternalRequest
- Response translation: InternalResponse → Claude-compatible JSON
- Content normalization (string, blocks, system prompts)
- Tool normalization
- Thinking normalization
- Response shape matches API_SPEC.md §4.5
"""

from routeflow.api.models import (
    ContentBlock,
    CreateMessageRequest,
    Message,
    ThinkingConfig,
    ToolDefinition,
)
from routeflow.core.schemas import (
    ContentBlockType,
    InternalResponse,
    InternalResponseBlock,
    InternalUsage,
    StopReason,
)
from routeflow.translator.request import translate_request
from routeflow.translator.response import translate_response

# ===========================================================================
# Request translation tests
# ===========================================================================


class TestTranslateRequestBasic:
    """Test basic request translation from gateway to internal model."""

    def test_simple_text_message(self) -> None:
        """Plain string content should become a single text block."""
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hello")],
            max_tokens=100,
        )
        result = translate_request(api_req, request_id="req_001")

        assert result.model == "claude-sonnet-4-20250514"
        assert len(result.messages) == 1
        assert result.messages[0].role == "user"
        assert len(result.messages[0].content) == 1
        assert result.messages[0].content[0].type == ContentBlockType.TEXT
        assert result.messages[0].content[0].text == "Hello"

    def test_max_tokens_preserved(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=500,
        )
        result = translate_request(api_req)
        assert result.max_tokens == 500

    def test_stream_flag_preserved(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
            stream=True,
        )
        result = translate_request(api_req)
        assert result.stream is True

    def test_stream_flag_default_false(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
        )
        result = translate_request(api_req)
        assert result.stream is False

    def test_temperature_preserved(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
            temperature=0.7,
        )
        result = translate_request(api_req)
        assert result.temperature == 0.7

    def test_temperature_none_by_default(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
        )
        result = translate_request(api_req)
        assert result.temperature is None

    def test_request_id_carried_in_metadata(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
        )
        result = translate_request(api_req, request_id="req_abc123")
        assert result.metadata.request_id == "req_abc123"

    def test_request_id_defaults_to_empty(self) -> None:
        api_req = CreateMessageRequest(
            model="claude-sonnet-4-20250514",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
        )
        result = translate_request(api_req)
        assert result.metadata.request_id == ""


# ---------------------------------------------------------------------------
# Content normalization tests
# ---------------------------------------------------------------------------


class TestContentNormalization:
    """Test content normalization from gateway to internal blocks."""

    def test_string_content_becomes_text_block(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hello world")],
            max_tokens=10,
        )
        result = translate_request(api_req)
        blocks = result.messages[0].content
        assert len(blocks) == 1
        assert blocks[0].type == ContentBlockType.TEXT
        assert blocks[0].text == "Hello world"

    def test_text_content_block(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="user",
                    content=[ContentBlock(type="text", text="Block text")],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        blocks = result.messages[0].content
        assert len(blocks) == 1
        assert blocks[0].type == ContentBlockType.TEXT
        assert blocks[0].text == "Block text"

    def test_image_content_block(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlock(
                            type="image",
                            source={"type": "base64", "media_type": "image/png", "data": "abc"},
                        )
                    ],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        blocks = result.messages[0].content
        assert len(blocks) == 1
        assert blocks[0].type == ContentBlockType.IMAGE
        assert blocks[0].image_source is not None
        assert blocks[0].image_source["type"] == "base64"

    def test_tool_use_content_block(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="assistant",
                    content=[
                        ContentBlock(
                            type="tool_use",
                            id="tu_1",
                            name="get_weather",
                            input={"city": "London"},
                        )
                    ],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        block = result.messages[0].content[0]
        assert block.type == ContentBlockType.TOOL_USE
        assert block.tool_use_id == "tu_1"
        assert block.tool_name == "get_weather"
        assert block.tool_input == {"city": "London"}

    def test_tool_result_content_block_string(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlock(
                            type="tool_result",
                            tool_use_id="tu_1",
                            content="Sunny",
                        )
                    ],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        block = result.messages[0].content[0]
        assert block.type == ContentBlockType.TOOL_RESULT
        assert block.tool_result_id == "tu_1"
        assert block.tool_result_content == "Sunny"

    def test_tool_result_content_block_nested_blocks(self) -> None:
        """Tool result with nested content blocks should concatenate text."""
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlock(
                            type="tool_result",
                            tool_use_id="tu_2",
                            content=[
                                ContentBlock(type="text", text="Part 1. "),
                                ContentBlock(type="text", text="Part 2."),
                            ],
                        )
                    ],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        block = result.messages[0].content[0]
        assert block.type == ContentBlockType.TOOL_RESULT
        assert block.tool_result_id == "tu_2"
        assert block.tool_result_content == "Part 1. Part 2."

    def test_thinking_content_block(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="assistant",
                    content=[ContentBlock(type="thinking", text="Let me think...")],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        block = result.messages[0].content[0]
        assert block.type == ContentBlockType.THINKING
        assert block.thinking_text == "Let me think..."

    def test_multi_block_content(self) -> None:
        """Multiple content blocks in one message should all be normalized."""
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(
                    role="user",
                    content=[
                        ContentBlock(type="text", text="Look at this"),
                        ContentBlock(
                            type="image",
                            source={"type": "url", "url": "https://example.com/img.png"},
                        ),
                    ],
                )
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        blocks = result.messages[0].content
        assert len(blocks) == 2
        assert blocks[0].type == ContentBlockType.TEXT
        assert blocks[1].type == ContentBlockType.IMAGE


# ---------------------------------------------------------------------------
# System prompt normalization tests
# ---------------------------------------------------------------------------


class TestSystemNormalization:
    """Test system prompt normalization."""

    def test_no_system_prompt(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
        )
        result = translate_request(api_req)
        assert result.system == []

    def test_string_system_prompt(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            system="You are a helpful assistant.",
        )
        result = translate_request(api_req)
        assert len(result.system) == 1
        assert result.system[0].type == ContentBlockType.TEXT
        assert result.system[0].text == "You are a helpful assistant."

    def test_list_system_prompt(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            system=[
                {"type": "text", "text": "Rule 1: Be helpful."},
                {"type": "text", "text": "Rule 2: Be concise."},
            ],
        )
        result = translate_request(api_req)
        assert len(result.system) == 2
        assert result.system[0].text == "Rule 1: Be helpful."
        assert result.system[1].text == "Rule 2: Be concise."

    def test_empty_string_system_prompt(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            system="",
        )
        result = translate_request(api_req)
        assert len(result.system) == 1
        assert result.system[0].text == ""


# ---------------------------------------------------------------------------
# Multi-message conversation tests
# ---------------------------------------------------------------------------


class TestMultiMessageConversation:
    """Test translation of multi-turn conversations."""

    def test_two_turn_conversation(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[
                Message(role="user", content="What is 2+2?"),
                Message(role="assistant", content="4"),
                Message(role="user", content="And 3+3?"),
            ],
            max_tokens=10,
        )
        result = translate_request(api_req)
        assert len(result.messages) == 3
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"
        assert result.messages[2].role == "user"
        assert result.messages[0].content[0].text == "What is 2+2?"
        assert result.messages[1].content[0].text == "4"
        assert result.messages[2].content[0].text == "And 3+3?"


# ---------------------------------------------------------------------------
# Tool normalization tests
# ---------------------------------------------------------------------------


class TestToolNormalization:
    """Test tool definition normalization."""

    def test_no_tools(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
        )
        result = translate_request(api_req)
        assert result.tools is None

    def test_single_tool(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            tools=[
                ToolDefinition(
                    name="search",
                    description="Search the web",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                )
            ],
        )
        result = translate_request(api_req)
        assert result.tools is not None
        assert len(result.tools) == 1
        assert result.tools[0].name == "search"
        assert result.tools[0].description == "Search the web"
        assert "properties" in result.tools[0].input_schema

    def test_multiple_tools(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            tools=[
                ToolDefinition(name="tool_a"),
                ToolDefinition(name="tool_b"),
                ToolDefinition(name="tool_c"),
            ],
        )
        result = translate_request(api_req)
        assert result.tools is not None
        assert len(result.tools) == 3
        assert [t.name for t in result.tools] == ["tool_a", "tool_b", "tool_c"]

    def test_tool_choice_preserved(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            tools=[ToolDefinition(name="search")],
            tool_choice={"type": "any"},
        )
        result = translate_request(api_req)
        assert result.tool_choice == {"type": "any"}


# ---------------------------------------------------------------------------
# Thinking normalization tests
# ---------------------------------------------------------------------------


class TestThinkingNormalization:
    """Test thinking config normalization."""

    def test_no_thinking(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
        )
        result = translate_request(api_req)
        assert result.thinking is None

    def test_thinking_enabled(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            thinking=ThinkingConfig(type="enabled", budget_tokens=500),
        )
        result = translate_request(api_req)
        assert result.thinking is not None
        assert result.thinking.enabled is True
        assert result.thinking.budget_tokens == 500

    def test_thinking_disabled(self) -> None:
        api_req = CreateMessageRequest(
            model="m",
            messages=[Message(role="user", content="Hi")],
            max_tokens=10,
            thinking=ThinkingConfig(type="disabled"),
        )
        result = translate_request(api_req)
        assert result.thinking is not None
        assert result.thinking.enabled is False


# ===========================================================================
# Response translation tests
# ===========================================================================


class TestTranslateResponseBasic:
    """Test basic response translation from internal to Claude-compatible."""

    def test_single_text_response(self) -> None:
        internal = InternalResponse(
            id="msg_001",
            role="assistant",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Hello!")],
            model="claude-sonnet-4-20250514",
            stop_reason=StopReason.END_TURN,
            usage=InternalUsage(input_tokens=10, output_tokens=5),
        )
        result = translate_response(internal)

        assert result["id"] == "msg_001"
        assert result["type"] == "message"
        assert result["role"] == "assistant"
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["stop_reason"] == "end_turn"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello!"
        assert result["usage"]["input_tokens"] == 10
        assert result["usage"]["output_tokens"] == 5

    def test_empty_content_response(self) -> None:
        internal = InternalResponse(id="msg_002", model="m")
        result = translate_response(internal)
        assert result["content"] == []

    def test_stop_reason_max_tokens(self) -> None:
        internal = InternalResponse(
            id="msg_003",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Truncated...")],
            model="m",
            stop_reason=StopReason.MAX_TOKENS,
        )
        result = translate_response(internal)
        assert result["stop_reason"] == "max_tokens"

    def test_stop_reason_tool_use(self) -> None:
        internal = InternalResponse(
            id="msg_004",
            model="m",
            stop_reason=StopReason.TOOL_USE,
        )
        result = translate_response(internal)
        assert result["stop_reason"] == "tool_use"


# ---------------------------------------------------------------------------
# Response content block formatting tests
# ---------------------------------------------------------------------------


class TestResponseContentBlocks:
    """Test response content block formatting."""

    def test_text_block_format(self) -> None:
        internal = InternalResponse(
            id="msg_010",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Answer is 42")],
            model="m",
        )
        result = translate_response(internal)
        block = result["content"][0]
        assert block == {"type": "text", "text": "Answer is 42"}

    def test_tool_use_block_format(self) -> None:
        internal = InternalResponse(
            id="msg_011",
            content=[
                InternalResponseBlock(
                    type=ContentBlockType.TOOL_USE,
                    tool_use_id="tu_1",
                    tool_name="search",
                    tool_input={"q": "weather"},
                )
            ],
            model="m",
            stop_reason=StopReason.TOOL_USE,
        )
        result = translate_response(internal)
        block = result["content"][0]
        assert block["type"] == "tool_use"
        assert block["id"] == "tu_1"
        assert block["name"] == "search"
        assert block["input"] == {"q": "weather"}

    def test_thinking_block_format(self) -> None:
        internal = InternalResponse(
            id="msg_012",
            content=[
                InternalResponseBlock(
                    type=ContentBlockType.THINKING,
                    thinking_text="I need to analyze this...",
                ),
                InternalResponseBlock(type=ContentBlockType.TEXT, text="Here's my answer."),
            ],
            model="m",
        )
        result = translate_response(internal)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "thinking"
        assert result["content"][0]["thinking"] == "I need to analyze this..."
        assert result["content"][1]["type"] == "text"
        assert result["content"][1]["text"] == "Here's my answer."

    def test_multi_block_response(self) -> None:
        """Response with text + tool_use blocks."""
        internal = InternalResponse(
            id="msg_013",
            content=[
                InternalResponseBlock(type=ContentBlockType.TEXT, text="I'll search for that."),
                InternalResponseBlock(
                    type=ContentBlockType.TOOL_USE,
                    tool_use_id="tu_5",
                    tool_name="web_search",
                    tool_input={"query": "AI gateway"},
                ),
            ],
            model="m",
            stop_reason=StopReason.TOOL_USE,
        )
        result = translate_response(internal)
        assert len(result["content"]) == 2
        assert result["content"][0]["type"] == "text"
        assert result["content"][1]["type"] == "tool_use"


# ---------------------------------------------------------------------------
# Response usage tests
# ---------------------------------------------------------------------------


class TestResponseUsage:
    """Test usage information in translated responses."""

    def test_usage_format(self) -> None:
        internal = InternalResponse(
            id="msg_020",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Hi")],
            model="m",
            usage=InternalUsage(input_tokens=100, output_tokens=50),
        )
        result = translate_response(internal)
        assert result["usage"] == {"input_tokens": 100, "output_tokens": 50}

    def test_default_usage_zero(self) -> None:
        internal = InternalResponse(id="msg_021", model="m")
        result = translate_response(internal)
        assert result["usage"] == {"input_tokens": 0, "output_tokens": 0}


# ---------------------------------------------------------------------------
# Response shape compliance tests (API_SPEC.md §4.5)
# ---------------------------------------------------------------------------


class TestResponseShapeCompliance:
    """Verify translated response matches API_SPEC.md §4.5 shape."""

    def test_required_fields_present(self) -> None:
        internal = InternalResponse(
            id="msg_030",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Test")],
            model="test-model",
            stop_reason=StopReason.END_TURN,
            usage=InternalUsage(input_tokens=10, output_tokens=20),
        )
        result = translate_response(internal)

        required_keys = {"id", "type", "role", "content", "model", "stop_reason", "usage"}
        assert required_keys == set(result.keys())

    def test_type_is_message(self) -> None:
        internal = InternalResponse(id="msg_031", model="m")
        result = translate_response(internal)
        assert result["type"] == "message"

    def test_role_is_assistant(self) -> None:
        internal = InternalResponse(id="msg_032", model="m")
        result = translate_response(internal)
        assert result["role"] == "assistant"
