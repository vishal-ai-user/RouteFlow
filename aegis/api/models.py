"""AEGIS API models — Pydantic models for the external API surface.

These models define the Claude Code-compatible request and response shapes
for the gateway layer. They map directly to API_SPEC.md §4–§6.

These are external-facing models only. Internal models (InternalRequest, etc.)
belong in core/schemas.py and will be added in Milestone 3.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request models — POST /v1/messages (API_SPEC.md §4.5)
# ---------------------------------------------------------------------------


class ContentBlock(BaseModel):
    """A single content block within a message.

    Supports text, image, tool_use, and tool_result types.
    Validation is intentionally loose in the gateway — the translator
    layer (Milestone 3) will perform deeper semantic validation.
    """

    type: str
    text: str | None = None
    # Tool use fields
    id: str | None = None
    name: str | None = None
    input: dict | None = None
    # Tool result fields
    tool_use_id: str | None = None
    content: str | list[ContentBlock] | None = None
    # Image fields
    source: dict | None = None


class Message(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(..., description="One of: user, assistant")
    content: str | list[ContentBlock] = Field(
        ..., description="Text string or list of content blocks"
    )


class ToolDefinition(BaseModel):
    """A tool definition provided by the client."""

    name: str
    description: str | None = None
    input_schema: dict = Field(default_factory=dict)


class ThinkingConfig(BaseModel):
    """Configuration for extended thinking / reasoning."""

    type: str = "enabled"
    budget_tokens: int | None = None


class CreateMessageRequest(BaseModel):
    """Request body for POST /v1/messages.

    Matches the Anthropic Messages API shape for Claude Code compatibility.
    """

    model: str = Field(..., description="Model identifier")
    messages: list[Message] = Field(
        ..., min_length=1, description="Conversation messages (at least one)"
    )
    max_tokens: int = Field(..., gt=0, description="Maximum tokens to generate")
    system: str | list[dict] | None = Field(
        default=None, description="System prompt or system message blocks"
    )
    temperature: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Sampling temperature"
    )
    stream: bool = Field(default=False, description="Enable SSE streaming")
    tools: list[ToolDefinition] | None = Field(default=None, description="Tool definitions")
    tool_choice: dict | None = Field(default=None, description="Tool choice policy")
    thinking: ThinkingConfig | None = Field(
        default=None, description="Extended thinking configuration"
    )


# ---------------------------------------------------------------------------
# Request models — POST /v1/messages/count_tokens (API_SPEC.md §4.4)
# ---------------------------------------------------------------------------


class CountTokensRequest(BaseModel):
    """Request body for POST /v1/messages/count_tokens."""

    model: str = Field(..., description="Model identifier")
    messages: list[Message] = Field(..., min_length=1, description="Messages to count tokens for")
    system: str | list[dict] | None = None


# ---------------------------------------------------------------------------
# Response models (API_SPEC.md §4.3–§4.5)
# ---------------------------------------------------------------------------


class Usage(BaseModel):
    """Token usage information."""

    input_tokens: int = 0
    output_tokens: int = 0


class TextResponseBlock(BaseModel):
    """A text content block in a response."""

    type: str = "text"
    text: str = ""


class MessageResponse(BaseModel):
    """Non-streaming response for POST /v1/messages.

    Shape matches API_SPEC.md §4.5 non-streaming response.
    """

    id: str
    type: str = "message"
    role: str = "assistant"
    content: list[TextResponseBlock]
    model: str
    stop_reason: str
    usage: Usage


class CountTokensResponse(BaseModel):
    """Response for POST /v1/messages/count_tokens."""

    input_tokens: int


class ModelInfo(BaseModel):
    """A single model entry."""

    id: str
    type: str = "model"


class ModelsResponse(BaseModel):
    """Response for GET /v1/models."""

    data: list[ModelInfo]
