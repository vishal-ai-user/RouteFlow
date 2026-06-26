"""AEGIS request translator — Convert Claude-compatible payloads to internal models.

Follows ARCHITECTURE.md §7:
- Parse Claude-compatible input
- Normalize message history
- Normalize system prompts
- Normalize tools and tool calls
- Normalize thinking/reasoning hints
- Normalize stream preferences

Rules:
- Translation must not contain routing policy.
- Translation must not know pool health.
- Translation must not know about UI concerns.
"""

from __future__ import annotations

from aegis.api.models import (
    ContentBlock,
    CreateMessageRequest,
    Message,
    ThinkingConfig,
    ToolDefinition,
)
from aegis.core.schemas import (
    ContentBlockType,
    InternalContentBlock,
    InternalMessage,
    InternalRequest,
    InternalRequestMetadata,
    InternalThinkingConfig,
    InternalToolDefinition,
)


def translate_request(
    api_request: CreateMessageRequest,
    request_id: str = "",
) -> InternalRequest:
    """Convert a Claude-compatible gateway request into an InternalRequest.

    This is the main entry point for request translation. It normalizes
    all fields into the provider-agnostic internal model.

    Args:
        api_request: The validated gateway request model.
        request_id: The per-request ID from middleware (for tracing).

    Returns:
        A fully normalized InternalRequest.
    """
    return InternalRequest(
        model=api_request.model,
        messages=_normalize_messages(api_request.messages),
        system=_normalize_system(api_request.system),
        max_tokens=api_request.max_tokens,
        temperature=api_request.temperature,
        stream=api_request.stream,
        tools=_normalize_tools(api_request.tools),
        tool_choice=api_request.tool_choice,
        thinking=_normalize_thinking(api_request.thinking),
        metadata=InternalRequestMetadata(request_id=request_id),
    )


def _normalize_content(
    content: str | list[ContentBlock],
) -> list[InternalContentBlock]:
    """Normalize message content to a list of typed internal blocks.

    If the content is a plain string, it is wrapped in a single text block.
    If the content is a list of ContentBlock, each is converted to its
    internal representation.
    """
    if isinstance(content, str):
        return [InternalContentBlock(type=ContentBlockType.TEXT, text=content)]

    blocks: list[InternalContentBlock] = []
    for block in content:
        blocks.append(_convert_content_block(block))
    return blocks


def _convert_content_block(block: ContentBlock) -> InternalContentBlock:
    """Convert a single gateway ContentBlock to an InternalContentBlock."""
    block_type = block.type

    if block_type == "text":
        return InternalContentBlock(
            type=ContentBlockType.TEXT,
            text=block.text or "",
        )

    if block_type == "image":
        return InternalContentBlock(
            type=ContentBlockType.IMAGE,
            image_source=block.source,
        )

    if block_type == "tool_use":
        return InternalContentBlock(
            type=ContentBlockType.TOOL_USE,
            tool_use_id=block.id,
            tool_name=block.name,
            tool_input=block.input or {},
        )

    if block_type == "tool_result":
        # tool_result content can be a string or nested blocks.
        # Normalize to a string for the internal model.
        result_content: str | None = None
        if isinstance(block.content, str):
            result_content = block.content
        elif isinstance(block.content, list):
            # Concatenate text from nested blocks.
            parts = [b.text for b in block.content if b.text]
            result_content = "".join(parts) if parts else None

        return InternalContentBlock(
            type=ContentBlockType.TOOL_RESULT,
            tool_result_id=block.tool_use_id,
            tool_result_content=result_content,
        )

    if block_type == "thinking":
        return InternalContentBlock(
            type=ContentBlockType.THINKING,
            thinking_text=block.text,
        )

    # Unknown block type — preserve as text with whatever text is available.
    return InternalContentBlock(
        type=ContentBlockType.TEXT,
        text=block.text or "",
    )


def _normalize_system(
    system: str | list[dict] | None,
) -> list[InternalContentBlock]:
    """Normalize the system prompt to a list of internal content blocks.

    - If None, returns an empty list.
    - If a string, wraps in a single text block.
    - If a list of dicts (system message blocks), converts each to a text block.
    """
    if system is None:
        return []

    if isinstance(system, str):
        return [InternalContentBlock(type=ContentBlockType.TEXT, text=system)]

    blocks: list[InternalContentBlock] = []
    for item in system:
        text = item.get("text", "")
        blocks.append(InternalContentBlock(type=ContentBlockType.TEXT, text=text))
    return blocks


def _normalize_messages(
    messages: list[Message],
) -> list[InternalMessage]:
    """Normalize a list of gateway messages to internal messages."""
    return [
        InternalMessage(
            role=msg.role,
            content=_normalize_content(msg.content),
        )
        for msg in messages
    ]


def _normalize_tools(
    tools: list[ToolDefinition] | None,
) -> list[InternalToolDefinition] | None:
    """Normalize tool definitions to internal form.

    Returns None if no tools are provided.
    """
    if tools is None:
        return None

    return [
        InternalToolDefinition(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
        )
        for tool in tools
    ]


def _normalize_thinking(
    thinking: ThinkingConfig | None,
) -> InternalThinkingConfig | None:
    """Normalize thinking configuration to internal form.

    Returns None if no thinking config is provided.
    """
    if thinking is None:
        return None

    return InternalThinkingConfig(
        enabled=thinking.type == "enabled",
        budget_tokens=thinking.budget_tokens,
    )
