"""AEGIS persistence models — Pydantic data schemas representing database rows.

Follows ARCHITECTURE.md §10.
"""

from __future__ import annotations

from pydantic import BaseModel


class Setting(BaseModel):
    """Represents a global application setting record."""

    key: str
    value: str
    updated_at: str


class ProviderRecord(BaseModel):
    """Represents a configured NVIDIA provider member."""

    id: int | None = None
    provider_id: str
    display_name: str
    api_key_encrypted: str
    base_url: str
    enabled: bool
    created_at: str
    updated_at: str


class ModelMapping(BaseModel):
    """Represents a mapping from logical model to upstream provider model."""

    id: int | None = None
    logical_model: str
    nvidia_model: str
    created_at: str
    updated_at: str


class RequestLog(BaseModel):
    """Represents a logged client request."""

    id: int | None = None
    request_id: str
    model: str
    stream: bool
    status_code: int | None = None
    latency_ms: int | None = None
    created_at: str


class ResponseLog(BaseModel):
    """Represents the cumulative textual response of a completed request."""

    id: int | None = None
    request_id: str
    content: str | None = None
    stop_reason: str | None = None
    created_at: str


class ErrorLog(BaseModel):
    """Represents a failure logged during request processing."""

    id: int | None = None
    request_id: str | None = None
    error_type: str
    error_message: str
    created_at: str


class UsageEntry(BaseModel):
    """Represents token usage statistics associated with a request."""

    id: int | None = None
    request_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str
