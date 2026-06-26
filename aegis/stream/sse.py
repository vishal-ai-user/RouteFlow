"""AEGIS SSE FastAPI integration — Builds StreamingResponse for the gateway.

Follows ARCHITECTURE.md §11, API_SPEC.md §4.6, and streaming rules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from aegis.core.schemas import InternalResponseBlock
from aegis.stream.encoder import encode_sse_event
from aegis.stream.normalizer import normalize_stream


def sse_streaming_response(
    blocks_iterator: AsyncIterator[InternalResponseBlock],
    message_id: str,
    model: str,
    input_tokens: int = 0,
) -> StreamingResponse:
    """Wrap normalizer and SSE encoder into a FastAPI StreamingResponse."""

    async def sse_event_generator() -> AsyncIterator[str]:
        # Chain normalization and encoding
        event_dict_stream = normalize_stream(
            blocks_iterator=blocks_iterator,
            message_id=message_id,
            model=model,
            input_tokens=input_tokens,
        )

        async for event in event_dict_stream:
            yield encode_sse_event(event)

    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for Nginx proxy compatibility
        },
    )
