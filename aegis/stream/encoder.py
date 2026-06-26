"""AEGIS SSE encoding — Format dictionaries to SSE protocol text.

Follows API_SPEC.md §4.6.
"""

from __future__ import annotations

import json


def encode_sse_event(event: dict) -> str:
    """Format an event dictionary into SSE protocol wire-format.

    Example:
        >>> encode_sse_event({"type": "message_stop"})
        'event: message_stop\ndata: {"type": "message_stop"}\n\n'
    """
    event_type = event.get("type", "message_delta")
    data_json = json.dumps(event)
    return f"event: {event_type}\ndata: {data_json}\n\n"
