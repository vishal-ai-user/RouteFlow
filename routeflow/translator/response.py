"""RouteFlow response translator — Convert internal responses to Claude-compatible output.

Follows ARCHITECTURE.md §7:
- Convert internal responses back to Anthropic-style output.

Output must match API_SPEC.md §4.5 non-streaming response shape:
    {
        "id": "msg_001",
        "type": "message",
        "role": "assistant",
        "content": [...],
        "model": "...",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": ..., "output_tokens": ...}
    }

Rules:
- No provider-specific logic.
- No streaming concerns (SSE is handled in the streaming layer).
- No routing or pool knowledge.
"""

from __future__ import annotations

from routeflow.core.schemas import (
    ContentBlockType,
    InternalResponse,
    InternalResponseBlock,
    InternalUsage,
)


def translate_response(internal_response: InternalResponse) -> dict:
    """Convert an InternalResponse to a Claude-compatible JSON dict.

    Args:
        internal_response: The provider-agnostic response from the adapter.

    Returns:
        A dict matching the Anthropic Messages API non-streaming response shape.
    """
    return {
        "id": internal_response.id,
        "type": "message",
        "role": internal_response.role,
        "content": [_format_content_block(block) for block in internal_response.content],
        "model": internal_response.model,
        "stop_reason": internal_response.stop_reason.value,
        "usage": _format_usage(internal_response.usage),
    }


def _format_content_block(block: InternalResponseBlock) -> dict:
    """Format a single internal response block to Anthropic-compatible dict."""
    if block.type == ContentBlockType.TEXT:
        return {
            "type": "text",
            "text": block.text or "",
        }

    if block.type == ContentBlockType.TOOL_USE:
        return {
            "type": "tool_use",
            "id": block.tool_use_id or "",
            "name": block.tool_name or "",
            "input": block.tool_input or {},
        }

    if block.type == ContentBlockType.THINKING:
        return {
            "type": "thinking",
            "thinking": block.thinking_text or "",
        }

    # Fallback for unknown types — render as text.
    return {
        "type": "text",
        "text": block.text or "",
    }


def _format_usage(usage: InternalUsage) -> dict:
    """Format usage information to Anthropic-compatible dict."""
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
