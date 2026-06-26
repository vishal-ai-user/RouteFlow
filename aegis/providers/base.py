"""AEGIS base provider — Abstract interface for all downstream LLM adapters.

Follows ARCHITECTURE.md §10:
- Defines the common contract for LLM provider adapters.
- Consumes InternalRequest and returns InternalResponse.
- Fully decoupled from gateway and API layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from aegis.core.schemas import InternalRequest, InternalResponse, InternalResponseBlock


class BaseProvider(ABC):
    """Abstract base class for all AEGIS LLM provider adapters."""

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model_mapping: dict[str, str] | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """Initialize the provider adapter.

        Args:
            name: Human-readable identifier for this instance (e.g. pool member ID).
            api_key: Secret API credential for the provider.
            base_url: Configurable service endpoint URL.
            model_mapping: Dictionary mapping client model IDs to provider model IDs.
            timeout_seconds: Network timeout duration for request execution.
        """
        self.name = name
        self.api_key = api_key
        self.base_url = base_url
        self.model_mapping = model_mapping or {}
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    async def complete(self, request: InternalRequest) -> InternalResponse:
        """Execute a non-streaming completion request.

        Args:
            request: The normalized internal request object.

        Returns:
            A normalized internal response object.
        """
        pass

    @abstractmethod
    def complete_stream(self, request: InternalRequest) -> AsyncIterator[InternalResponseBlock]:
        """Execute a streaming completion request.

        Args:
            request: The normalized internal request object.

        Yields:
            Normalized internal response content blocks as they arrive.
        """
        pass
