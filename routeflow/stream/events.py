"""RouteFlow streaming event definitions.

Follows API_SPEC.md §4.6 and API_SPEC.md §5 event contracts.
- Defines standard dict structures for Claude-compatible Server-Sent Events.
"""

from __future__ import annotations

from typing import Any


def message_start(
    message_id: str,
    model: str,
    input_tokens: int = 0,
) -> dict[str, Any]:
    """Build a message_start event payload."""
    return {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": 0,
            },
        },
    }


def content_block_start(
    index: int,
    block_type: str,
    tool_id: str | None = None,
    tool_name: str | None = None,
) -> dict[str, Any]:
    """Build a content_block_start event payload."""
    content_block: dict[str, Any] = {"type": block_type}
    if block_type == "text":
        content_block["text"] = ""
    elif block_type == "thinking":
        content_block["thinking"] = ""
    elif block_type == "tool_use" and tool_id and tool_name:
        content_block["id"] = tool_id
        content_block["name"] = tool_name
        content_block["input"] = {}

    return {
        "type": "content_block_start",
        "index": index,
        "content_block": content_block,
    }


def content_block_delta(
    index: int,
    delta_type: str,
    text: str | None = None,
    thinking: str | None = None,
    partial_json: str | None = None,
) -> dict[str, Any]:
    """Build a content_block_delta event payload."""
    delta: dict[str, Any] = {"type": delta_type}
    if delta_type == "text_delta" and text is not None:
        delta["text"] = text
    elif delta_type == "thinking_delta" and thinking is not None:
        delta["thinking"] = thinking
    elif delta_type == "input_json_delta" and partial_json is not None:
        delta["partial_json"] = partial_json

    return {
        "type": "content_block_delta",
        "index": index,
        "delta": delta,
    }


def content_block_stop(index: int) -> dict[str, Any]:
    """Build a content_block_stop event payload."""
    return {
        "type": "content_block_stop",
        "index": index,
    }


def message_delta(
    stop_reason: str | None = "end_turn",
    output_tokens: int = 0,
) -> dict[str, Any]:
    """Build a message_delta event payload."""
    return {
        "type": "message_delta",
        "delta": {
            "stop_reason": stop_reason,
            "stop_sequence": None,
        },
        "usage": {
            "output_tokens": output_tokens,
        },
    }


def message_stop() -> dict[str, Any]:
    """Build a message_stop event payload."""
    return {
        "type": "message_stop",
    }


def error_event(error_type: str, message: str) -> dict[str, Any]:
    """Build a streaming error event payload."""
    return {
        "type": "error",
        "error": {
            "type": error_type,
            "message": message,
        },
    }
