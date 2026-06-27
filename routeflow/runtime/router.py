"""RouteFlow runtime router — Coordinates selection, load-tracking, retry, and failover.

Follows ARCHITECTURE.md §8 and router rules:
- Orchestrates InternalRequest -> Pool selection -> Execution -> Response.
- Does not contain provider-specific serialization or HTTP transport details.
- Manages active request metrics and health updates.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from routeflow.core.errors import RouteFlowError, ErrorType
from routeflow.core.logging import get_logger
from routeflow.runtime.health import handle_provider_failure, handle_provider_success
from routeflow.runtime.retry import is_retryable_error

if TYPE_CHECKING:
    from routeflow.core.schemas import InternalRequest, InternalResponse, InternalResponseBlock
    from routeflow.providers.pool import ProviderPool
    from routeflow.runtime.scheduler import Scheduler

logger = get_logger(__name__)


class RuntimeRouter:
    """Orchestrates runtime routing, load-tracking, failover, and retry execution."""

    def __init__(
        self,
        pool: ProviderPool,
        scheduler: Scheduler,
        max_retries: int = 2,
        cooldown_duration_seconds: int = 30,
        consecutive_failure_threshold: int = 3,
    ) -> None:
        self.pool = pool
        self.scheduler = scheduler
        self.max_retries = max_retries
        self.cooldown_duration_seconds = cooldown_duration_seconds
        self.consecutive_failure_threshold = consecutive_failure_threshold

    async def route(self, request: InternalRequest) -> InternalResponse:
        """Route a non-streaming request to an eligible provider with failover support."""
        attempt = 0
        tried_provider_ids: set[str] = set()

        while True:
            # 1. Retrieve eligible pool members
            eligible = self.pool.retrieve_eligible_providers()

            # 2. Filter out already tried members to avoid cycling on the same error
            untried_eligible = [m for m in eligible if m.provider_id not in tried_provider_ids]

            # 3. If no eligible untried providers are left, raise provider error
            if not untried_eligible:
                logger.error("No eligible untried providers available for routing.")
                raise RouteFlowError(
                    ErrorType.PROVIDER_ERROR,
                    "All eligible providers failed or none are registered.",
                )

            # 4. Select the provider member
            member = self.scheduler.select(untried_eligible)
            tried_provider_ids.add(member.provider_id)

            # Set provider_id context variable for logging
            from routeflow.core.logging import provider_id_var

            provider_id_var.set(member.provider_id)

            # 5. Increment load counters
            self.pool.increment_active_requests(member.provider_id)
            logger.info(
                "Attempt %d: Routing request to provider %s (active: %d)",
                attempt + 1,
                member.provider_id,
                member.active_requests,
            )

            try:
                # 6. Execute the call via adapter
                response = await member.provider.complete(request)

                # 7. Record success and decrement active load
                self.pool.decrement_active_requests(member.provider_id)
                handle_provider_success(member)

                return response

            except Exception as exc:
                # 8. Record failure and decrement active load
                self.pool.decrement_active_requests(member.provider_id)
                handle_provider_failure(
                    member,
                    cooldown_duration_seconds=self.cooldown_duration_seconds,
                    failure_threshold=self.consecutive_failure_threshold,
                )

                logger.warning(
                    "Provider %s execution failed: %s",
                    member.provider_id,
                    str(exc),
                )

                # 9. Evaluate retry eligibility
                if is_retryable_error(exc) and attempt < self.max_retries:
                    attempt += 1
                    logger.info("Failure is retryable. Initiating failover retry %d...", attempt)
                    continue

                # Not retryable or retry count exceeded: propagate
                raise

    async def route_stream(self, request: InternalRequest) -> AsyncIterator[InternalResponseBlock]:
        """Route a streaming request to an eligible provider.

        Failover is only supported at the connection level (before yielding chunks).
        """
        attempt = 0
        tried_provider_ids: set[str] = set()

        while True:
            # 1. Retrieve eligible pool members
            eligible = self.pool.retrieve_eligible_providers()
            untried_eligible = [m for m in eligible if m.provider_id not in tried_provider_ids]

            if not untried_eligible:
                logger.error("No eligible untried providers available for stream routing.")
                raise RouteFlowError(
                    ErrorType.PROVIDER_ERROR,
                    "All eligible providers failed or none are registered.",
                )

            # 2. Select the provider member
            member = self.scheduler.select(untried_eligible)
            tried_provider_ids.add(member.provider_id)

            # Set provider_id context variable for logging
            from routeflow.core.logging import provider_id_var

            provider_id_var.set(member.provider_id)

            # 3. Increment active requests
            self.pool.increment_active_requests(member.provider_id)
            logger.info(
                "Attempt %d: Routing stream to provider %s (active: %d)",
                attempt + 1,
                member.provider_id,
                member.active_requests,
            )

            connected = False
            try:
                # Get the stream generator
                stream_generator = member.provider.complete_stream(request)

                # To support connection-level failover, execute the initial iteration step.
                # If it raises an exception during the first step, catch it and fail over.
                iterator = stream_generator.__aiter__()
                try:
                    first_block = await iterator.__anext__()
                except StopAsyncIteration:
                    # Stream was empty, which is a success. Decrement load and return.
                    self.pool.decrement_active_requests(member.provider_id)
                    handle_provider_success(member)
                    return

                connected = True

            except Exception as exc:
                # Connection failed before yielding data
                self.pool.decrement_active_requests(member.provider_id)
                handle_provider_failure(
                    member,
                    cooldown_duration_seconds=self.cooldown_duration_seconds,
                    failure_threshold=self.consecutive_failure_threshold,
                )

                logger.warning(
                    "Provider %s stream connection failed: %s",
                    member.provider_id,
                    str(exc),
                )

                if is_retryable_error(exc) and attempt < self.max_retries:
                    attempt += 1
                    logger.info(
                        "Stream failure is retryable. Initiating failover retry %d...",
                        attempt,
                    )
                    continue

                raise

            # If we connected successfully, we break the retry/failover loop and consume the stream
            if connected:
                break

        # Yield the blocks and ensure cleanup on success, failure, or cancellation (GeneratorExit)
        active_decremented = False
        try:
            yield first_block
            async for block in iterator:
                yield block
            self.pool.decrement_active_requests(member.provider_id)
            active_decremented = True
            handle_provider_success(member)
        except Exception as stream_exc:
            self.pool.decrement_active_requests(member.provider_id)
            active_decremented = True
            handle_provider_failure(
                member,
                cooldown_duration_seconds=self.cooldown_duration_seconds,
                failure_threshold=self.consecutive_failure_threshold,
            )
            raise stream_exc
        finally:
            if not active_decremented:
                self.pool.decrement_active_requests(member.provider_id)
