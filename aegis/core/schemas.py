"""AEGIS internal schemas — Provider-agnostic request and response models.

These models decouple the gateway API surface (api/models.py) from
provider-specific payloads. All layers below the gateway (translator,
runtime, provider adapter) operate on these internal types.

Design rules (ARCHITECTURE.md §7, §20):
- Content is always a list of typed blocks (never a raw string).
- System prompt is always a list of blocks.
- Models are fully typed with Pydantic.
- No provider-specific fields leak into these models.
- request_id is carried in metadata for tracing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContentBlockType(StrEnum):
    """Types of content blocks in messages and responses."""

    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"


class StopReason(StrEnum):
    """Reasons a model may stop generating.

    Maps to Anthropic stop_reason values (API_SPEC.md §4.5).
    """

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"


# ---------------------------------------------------------------------------
# Internal request models
# ---------------------------------------------------------------------------


class InternalContentBlock(BaseModel):
    """A single normalized content block.

    All message content is normalized to a list of these blocks,
    regardless of whether the client sent a plain string or structured list.
    """

    type: ContentBlockType
    text: str | None = None

    # Tool use fields (type == tool_use)
    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None

    # Tool result fields (type == tool_result)
    tool_result_id: str | None = None
    tool_result_content: str | None = None

    # Image fields (type == image)
    image_source: dict | None = None

    # Thinking fields (type == thinking)
    thinking_text: str | None = None


class InternalMessage(BaseModel):
    """A normalized message in the conversation history.

    Content is always a list of InternalContentBlock, never a raw string.
    """

    role: str
    content: list[InternalContentBlock]


class InternalToolDefinition(BaseModel):
    """A tool definition in internal form."""

    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)


class InternalThinkingConfig(BaseModel):
    """Thinking/reasoning configuration in internal form."""

    enabled: bool = True
    budget_tokens: int | None = None


class InternalRequestMetadata(BaseModel):
    """Per-request metadata for tracing and diagnostics."""

    request_id: str = ""


class InternalRequest(BaseModel):
    """Fully normalized internal request.

    This is the canonical representation used by the runtime and provider
    layers. It is produced by the translator from the gateway payload.
    """

    model: str
    messages: list[InternalMessage]
    system: list[InternalContentBlock] = Field(default_factory=list)
    max_tokens: int
    temperature: float | None = None
    stream: bool = False
    tools: list[InternalToolDefinition] | None = None
    tool_choice: dict | None = None
    thinking: InternalThinkingConfig | None = None
    metadata: InternalRequestMetadata = Field(default_factory=InternalRequestMetadata)


# ---------------------------------------------------------------------------
# Internal response models
# ---------------------------------------------------------------------------


class InternalUsage(BaseModel):
    """Token usage information from the provider."""

    input_tokens: int = 0
    output_tokens: int = 0


class InternalResponseBlock(BaseModel):
    """A single content block in a provider response.

    Covers text output, tool use output, and thinking blocks.
    """

    type: ContentBlockType
    text: str | None = None

    # Tool use response fields
    tool_use_id: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None

    # Thinking fields
    thinking_text: str | None = None


class InternalResponse(BaseModel):
    """Fully normalized internal response.

    This is the canonical representation produced by the provider adapter
    and consumed by the translator to produce client-facing output.
    """

    id: str
    role: str = "assistant"
    content: list[InternalResponseBlock] = Field(default_factory=list)
    model: str = ""
    stop_reason: StopReason = StopReason.END_TURN
    usage: InternalUsage = Field(default_factory=InternalUsage)
