"""AEGIS stream normalizer — Converts provider block streams into Claude SSE event dicts.

Follows ARCHITECTURE.md §11, API_SPEC.md §4.6, and streaming rules.
- Translates AsyncIterator[InternalResponseBlock] to AsyncIterator[dict].
- Provider-agnostic.
- Handles text, thinking, and tool_use blocks.
- Yields error events on connection/mid-stream exceptions.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from aegis.core.errors import AegisError
from aegis.core.logging import get_logger
from aegis.core.schemas import ContentBlockType, InternalResponseBlock
from aegis.stream import events

logger = get_logger(__name__)


async def normalize_stream(
    blocks_iterator: AsyncIterator[InternalResponseBlock],
    message_id: str,
    model: str,
    input_tokens: int = 0,
) -> AsyncIterator[dict]:
    """Normalize internal response blocks to a stream of Claude-compatible event dicts."""
    # 1. Emit message_start event
    yield events.message_start(message_id, model, input_tokens)

    current_index = -1
    current_block_type: ContentBlockType | None = None
    output_tokens_count = 0
    saw_tool_use = False

    try:
        async for block in blocks_iterator:
            # 2. Block transition logic: open new blocks
            if block.type != current_block_type:
                # If there was a previous open block (e.g. text/thinking), close it first
                if current_block_type is not None:
                    yield events.content_block_stop(current_index)

                current_index += 1
                current_block_type = block.type

                # Yield block start
                if block.type == ContentBlockType.TEXT:
                    yield events.content_block_start(current_index, "text")
                elif block.type == ContentBlockType.THINKING:
                    yield events.content_block_start(current_index, "thinking")
                elif block.type == ContentBlockType.TOOL_USE:
                    saw_tool_use = True
                    yield events.content_block_start(
                        current_index,
                        "tool_use",
                        tool_id=block.tool_use_id,
                        tool_name=block.tool_name,
                    )

            # 3. Yield deltas
            if block.type == ContentBlockType.TEXT:
                text_val = block.text or ""
                yield events.content_block_delta(current_index, "text_delta", text=text_val)
                output_tokens_count += max(1, len(text_val) // 4)

            elif block.type == ContentBlockType.THINKING:
                think_val = block.thinking_text or ""
                yield events.content_block_delta(
                    current_index, "thinking_delta", thinking=think_val
                )
                output_tokens_count += max(1, len(think_val) // 4)

            elif block.type == ContentBlockType.TOOL_USE:
                # Accumulate tool calls delta
                # Since adapter yields a completed tool use block, we serialize inputs
                tool_input_json = json.dumps(block.tool_input or {})
                yield events.content_block_delta(
                    current_index, "input_json_delta", partial_json=tool_input_json
                )
                # Output token estimation for tool calls
                output_tokens_count += max(1, len(tool_input_json) // 4)

                # Immediately close tool block since we yielded the full payload
                yield events.content_block_stop(current_index)
                current_block_type = None  # Reset so subsequent blocks trigger a start

        # 4. Stream loop ended successfully: close any remaining open block
        if current_block_type is not None:
            yield events.content_block_stop(current_index)

        # 5. Yield completion delta and stop events
        stop_reason = "tool_use" if saw_tool_use else "end_turn"
        yield events.message_delta(stop_reason=stop_reason, output_tokens=output_tokens_count)
        yield events.message_stop()

    except Exception as exc:
        logger.error("Exception raised during stream normalization: %s", str(exc))
        # Safely wrap internal messages
        err_msg = "An unexpected error occurred during streaming."
        err_type = "provider_error"

        if isinstance(exc, AegisError):
            err_msg = exc.message
            err_type = exc.error_type.value

        # Yield error SSE event and terminate
        yield events.error_event(err_type, err_msg)
