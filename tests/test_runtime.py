"""Unit tests for the RouteFlow runtime routing, pool, and scheduling layer.

Verifies:
- Registry states (registration, enabling/disabling, active requests)
- Scheduler selection policies (least-busy, health-first)
- Cooldown boundaries and automatic recovery
- Retry error classification
- Orchestrated failover and retry bounds
- Streaming connection-level failover and mid-stream error handling
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from routeflow.core.errors import ErrorType, RouteFlowError
from routeflow.core.schemas import (
    ContentBlockType,
    InternalRequest,
    InternalResponse,
    InternalResponseBlock,
    InternalUsage,
    StopReason,
)
from routeflow.providers.base import BaseProvider
from routeflow.providers.pool import PoolMember, ProviderPool
from routeflow.runtime.health import handle_provider_failure, handle_provider_success
from routeflow.runtime.retry import is_retryable_error
from routeflow.runtime.router import RuntimeRouter
from routeflow.runtime.scheduler import Scheduler

# ===========================================================================
# Mock Provider Adapter for Testing
# ===========================================================================


class MockTestProvider(BaseProvider):
    """Mock implementation of BaseProvider for unit testing."""

    def __init__(
        self,
        name: str,
        response_data: InternalResponse | Exception,
        stream_blocks: list[InternalResponseBlock] | Exception | None = None,
    ) -> None:
        super().__init__(name, "mock-key", "https://mock-endpoint")
        self.response_data = response_data
        self.stream_blocks = stream_blocks or []
        self.called_count = 0
        self.stream_called_count = 0

    async def complete(self, request: InternalRequest) -> InternalResponse:
        self.called_count += 1
        if isinstance(self.response_data, Exception):
            raise self.response_data
        return self.response_data

    async def complete_stream(
        self, request: InternalRequest
    ) -> AsyncIterator[InternalResponseBlock]:
        self.stream_called_count += 1
        if isinstance(self.stream_blocks, Exception):
            raise self.stream_blocks

        # Yield blocks
        for block in self.stream_blocks:
            yield block


# ===========================================================================
# Provider Pool Tests
# ===========================================================================


class TestProviderPoolRegistry:
    """Tests for ProviderPool and PoolMember state management."""

    def test_provider_registration_and_removal(self) -> None:
        pool = ProviderPool()
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "Provider 1", adapter)

        pool.register_provider(member)
        assert pool.get_provider("p1") is member

        pool.remove_provider("p1")
        assert pool.get_provider("p1") is None

    def test_enable_disable_states(self) -> None:
        pool = ProviderPool()
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "Provider 1", adapter, enabled=True)
        pool.register_provider(member)

        pool.disable_provider("p1")
        assert member.enabled is False
        assert pool.retrieve_eligible_providers() == []

        pool.enable_provider("p1")
        assert member.enabled is True
        assert pool.retrieve_eligible_providers() == [member]

    def test_active_requests_bounds(self) -> None:
        pool = ProviderPool()
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "Provider 1", adapter)
        pool.register_provider(member)

        pool.increment_active_requests("p1")
        assert member.active_requests == 1

        pool.decrement_active_requests("p1")
        assert member.active_requests == 0

        # Ensure it doesn't drop below 0
        pool.decrement_active_requests("p1")
        assert member.active_requests == 0

    def test_health_state_transitions(self) -> None:
        pool = ProviderPool()
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "Provider 1", adapter)
        pool.register_provider(member)

        pool.mark_unhealthy("p1")
        assert member.healthy is False

        pool.mark_healthy("p1")
        assert member.healthy is True

    def test_cooldown_eligibility_and_automatic_expiration(self) -> None:
        pool = ProviderPool()
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "Provider 1", adapter)
        pool.register_provider(member)

        # Apply active cooldown
        member.cooldown_expiry = datetime.now() + timedelta(seconds=10)
        assert pool.retrieve_eligible_providers() == []

        # Simulate expired cooldown
        member.cooldown_expiry = datetime.now() - timedelta(seconds=1)
        eligible = pool.retrieve_eligible_providers()

        # Cooldown should automatically expire, reset stats, and make member eligible again
        assert eligible == [member]
        assert member.cooldown_expiry is None
        assert member.healthy is True
        assert member.recent_failure_count == 0


# ===========================================================================
# Health & Cooldown Policy Tests
# ===========================================================================


class TestHealthCooldownPolicies:
    """Tests for handle_provider_success and handle_provider_failure."""

    def test_failure_increments_and_cooldown_trigger(self) -> None:
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "P1", adapter)

        # 1st failure
        handle_provider_failure(member, cooldown_duration_seconds=30, failure_threshold=3)
        assert member.recent_failure_count == 1
        assert member.healthy is True
        assert member.cooldown_expiry is None

        # 2nd failure
        handle_provider_failure(member, cooldown_duration_seconds=30, failure_threshold=3)
        assert member.recent_failure_count == 2
        assert member.healthy is True

        # 3rd failure (triggers cooldown)
        handle_provider_failure(member, cooldown_duration_seconds=30, failure_threshold=3)
        assert member.recent_failure_count == 3
        assert member.healthy is False
        assert member.cooldown_expiry is not None

    def test_success_resets_health_states(self) -> None:
        adapter = MockTestProvider("a", Exception("unused"))
        member = PoolMember("p1", "P1", adapter)

        member.recent_failure_count = 5
        member.healthy = False
        member.cooldown_expiry = datetime.now() + timedelta(seconds=60)

        handle_provider_success(member)

        assert member.recent_failure_count == 0
        assert member.healthy is True
        assert member.cooldown_expiry is None
        assert member.last_success is not None


# ===========================================================================
# Scheduler Selection Tests
# ===========================================================================


class TestSchedulerSelection:
    """Tests for scheduler routing selection logic."""

    def test_empty_eligible_list_raises(self) -> None:
        scheduler = Scheduler()
        with pytest.raises(RouteFlowError) as exc_info:
            scheduler.select([])
        assert exc_info.value.error_type == ErrorType.PROVIDER_ERROR

    def test_least_busy_selection(self) -> None:
        scheduler = Scheduler(mode="least-busy")
        adapter = MockTestProvider("a", Exception("unused"))

        m1 = PoolMember("p1", "P1", adapter)
        m1.active_requests = 5

        m2 = PoolMember("p2", "P2", adapter)
        m2.active_requests = 2

        m3 = PoolMember("p3", "P3", adapter)
        m3.active_requests = 8

        selected = scheduler.select([m1, m2, m3])
        assert selected is m2

    def test_health_first_selection(self) -> None:
        scheduler = Scheduler(mode="health-first")
        adapter = MockTestProvider("a", Exception("unused"))

        # Healthy but busy
        m1 = PoolMember("p1", "P1", adapter)
        m1.healthy = True
        m1.active_requests = 3

        # Unhealthy and idle
        m2 = PoolMember("p2", "P2", adapter)
        m2.healthy = False
        m2.active_requests = 0

        # Healthy and less busy
        m3 = PoolMember("p3", "P3", adapter)
        m3.healthy = True
        m3.active_requests = 1

        selected = scheduler.select([m1, m2, m3])
        # Should select the healthiest one with the lowest load
        assert selected is m3

    def test_health_first_fallback_when_all_unhealthy(self) -> None:
        scheduler = Scheduler(mode="health-first")
        adapter = MockTestProvider("a", Exception("unused"))

        m1 = PoolMember("p1", "P1", adapter)
        m1.healthy = False
        m1.recent_failure_count = 5
        m1.active_requests = 1

        m2 = PoolMember("p2", "P2", adapter)
        m2.healthy = False
        m2.recent_failure_count = 2
        m2.active_requests = 5

        m3 = PoolMember("p3", "P3", adapter)
        m3.healthy = False
        m3.recent_failure_count = 2
        m3.active_requests = 2

        selected = scheduler.select([m1, m2, m3])
        # Since all are unhealthy, choose the one with lowest failure count,
        # then lowest active requests
        assert selected is m3

    def test_round_robin_selection(self) -> None:
        scheduler = Scheduler(mode="round-robin")
        adapter = MockTestProvider("a", Exception("unused"))

        m1 = PoolMember("nvidia-1", "N1", adapter)
        m2 = PoolMember("nvidia-2", "N2", adapter)

        # Reset counter and cache to start clean
        Scheduler._round_robin_counter = 0
        Scheduler._last_selection_time = 0.0
        Scheduler._last_selected_member = None

        # 1. First request -> nvidia-1
        selected1 = scheduler.select([m1, m2])
        assert selected1 is m1

        # 2. Stickiness check: immediate second request should STILL return nvidia-1
        selected_sticky = scheduler.select([m1, m2])
        assert selected_sticky is m1

        # 3. Rotate check: simulate 3 seconds elapsed (by resetting time), should rotate to nvidia-2
        Scheduler._last_selection_time = 0.0
        selected2 = scheduler.select([m1, m2])
        assert selected2 is m2

        # 4. Rotate check again: simulate time elapsed, should loop back to nvidia-1
        Scheduler._last_selection_time = 0.0
        selected3 = scheduler.select([m1, m2])
        assert selected3 is m1



# ===========================================================================
# Retry Policy Tests
# ===========================================================================


def test_retry_policy_classifications() -> None:
    # Retryable cases
    assert is_retryable_error(RouteFlowError(ErrorType.RATE_LIMITED, "rate")) is True
    assert is_retryable_error(RouteFlowError(ErrorType.TIMEOUT, "timeout")) is True
    assert is_retryable_error(RouteFlowError(ErrorType.PROVIDER_ERROR, "upstream")) is True

    # Non-retryable cases
    assert is_retryable_error(RouteFlowError(ErrorType.UNAUTHORIZED, "auth")) is False
    assert is_retryable_error(RouteFlowError(ErrorType.VALIDATION_ERROR, "bad request")) is False
    assert is_retryable_error(RouteFlowError(ErrorType.INTERNAL_ERROR, "bug")) is False

    # General exceptions are not retryable
    assert is_retryable_error(ValueError("general error")) is False


# ===========================================================================
# Router Orchestration & Failover Tests
# ===========================================================================


class TestRouterOrchestration:
    """End-to-end routing, retry, active requests tracking, and failover integration tests."""

    @pytest.mark.asyncio
    async def test_successful_direct_route(self) -> None:
        pool = ProviderPool()
        mock_response = InternalResponse(
            id="r1",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="hello")],
            model="m",
            stop_reason=StopReason.END_TURN,
            usage=InternalUsage(),
        )
        adapter = MockTestProvider("adap-1", mock_response)
        member = PoolMember("p1", "Provider 1", adapter)
        pool.register_provider(member)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler)

        req = InternalRequest(model="m", messages=[], max_tokens=10)
        res = await router.route(req)

        assert res.id == "r1"
        assert adapter.called_count == 1
        assert member.active_requests == 0
        assert member.healthy is True
        assert member.recent_failure_count == 0

    @pytest.mark.asyncio
    async def test_failover_resolves_to_healthy_provider(self) -> None:
        pool = ProviderPool()

        # Provider 1: fails with retryable rate limit
        adapter1 = MockTestProvider("adap-1", RouteFlowError(ErrorType.RATE_LIMITED, "Over quota"))
        member1 = PoolMember("p1", "P1", adapter1)
        pool.register_provider(member1)

        # Provider 2: succeeds
        mock_response = InternalResponse(
            id="r2",
            content=[InternalResponseBlock(type=ContentBlockType.TEXT, text="resolved")],
            model="m",
            stop_reason=StopReason.END_TURN,
            usage=InternalUsage(),
        )
        adapter2 = MockTestProvider("adap-2", mock_response)
        member2 = PoolMember("p2", "P2", adapter2)
        pool.register_provider(member2)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=2)

        req = InternalRequest(model="m", messages=[], max_tokens=10)
        res = await router.route(req)

        # Verify failover resolved correctly
        assert res.id == "r2"
        assert adapter1.called_count == 1
        assert adapter2.called_count == 1

        # Check metrics
        assert member1.recent_failure_count == 1
        assert member2.recent_failure_count == 0
        assert member1.active_requests == 0
        assert member2.active_requests == 0

    @pytest.mark.asyncio
    async def test_retry_bounds_stops_at_limit(self) -> None:
        pool = ProviderPool()

        # Both providers fail with retryable timeouts
        adapter1 = MockTestProvider("adap-1", RouteFlowError(ErrorType.TIMEOUT, "Timeout"))
        member1 = PoolMember("p1", "P1", adapter1)
        pool.register_provider(member1)

        adapter2 = MockTestProvider("adap-2", RouteFlowError(ErrorType.TIMEOUT, "Timeout"))
        member2 = PoolMember("p2", "P2", adapter2)
        pool.register_provider(member2)

        # Set max_retries to 1 (total 2 attempts allowed)
        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=1)

        req = InternalRequest(model="m", messages=[], max_tokens=10)

        with pytest.raises(RouteFlowError) as exc_info:
            await router.route(req)

        assert exc_info.value.error_type == ErrorType.TIMEOUT
        # Total calls should equal max_retries + 1 = 2
        total_calls = adapter1.called_count + adapter2.called_count
        assert total_calls == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_does_not_failover(self) -> None:
        pool = ProviderPool()

        # Provider 1: Fails with unauthorized auth error (non-retryable)
        adapter1 = MockTestProvider("adap-1", RouteFlowError(ErrorType.UNAUTHORIZED, "Bad Key"))
        member1 = PoolMember("p1", "P1", adapter1)
        pool.register_provider(member1)

        # Provider 2: Healthy success
        adapter2 = MockTestProvider(
            "adap-2",
            InternalResponse(id="ok", model="m", usage=InternalUsage()),
        )
        member2 = PoolMember("p2", "P2", adapter2)
        pool.register_provider(member2)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=2)

        req = InternalRequest(model="m", messages=[], max_tokens=10)

        with pytest.raises(RouteFlowError) as exc_info:
            await router.route(req)

        assert exc_info.value.error_type == ErrorType.UNAUTHORIZED
        assert adapter1.called_count == 1
        # Provider 2 should never be called
        assert adapter2.called_count == 0

    @pytest.mark.asyncio
    async def test_stream_initial_connection_failover(self) -> None:
        pool = ProviderPool()

        # Provider 1: fails on connection (retryable timeout)
        adapter1 = MockTestProvider(
            "adap-1",
            Exception("unused"),
            stream_blocks=RouteFlowError(ErrorType.TIMEOUT, "Timeout"),
        )
        member1 = PoolMember("p1", "P1", adapter1)
        pool.register_provider(member1)

        # Provider 2: stream success
        blocks_data = [
            InternalResponseBlock(type=ContentBlockType.TEXT, text="Hi"),
            InternalResponseBlock(type=ContentBlockType.TEXT, text=" there"),
        ]
        adapter2 = MockTestProvider("adap-2", Exception("unused"), stream_blocks=blocks_data)
        member2 = PoolMember("p2", "P2", adapter2)
        pool.register_provider(member2)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=2)

        req = InternalRequest(model="m", messages=[], max_tokens=10)

        stream_blocks = []
        async for block in router.route_stream(req):
            stream_blocks.append(block)

        assert len(stream_blocks) == 2
        assert stream_blocks[0].text == "Hi"
        assert stream_blocks[1].text == " there"

        assert adapter1.stream_called_count == 1
        assert adapter2.stream_called_count == 1
        assert member1.recent_failure_count == 1
        assert member2.recent_failure_count == 0

    @pytest.mark.asyncio
    async def test_stream_mid_stream_error_does_not_failover(self) -> None:
        pool = ProviderPool()

        # Adapter that yields one block then raises an exception
        async def bad_stream_generator(
            request: InternalRequest,
        ) -> AsyncIterator[InternalResponseBlock]:
            yield InternalResponseBlock(type=ContentBlockType.TEXT, text="First block")
            raise RouteFlowError(ErrorType.PROVIDER_ERROR, "Mid-stream disconnect")

        adapter1 = MagicMock(spec=BaseProvider)
        adapter1.complete_stream.side_effect = bad_stream_generator
        member1 = PoolMember("p1", "P1", adapter1)
        pool.register_provider(member1)

        # Success fallback adapter
        adapter2 = MockTestProvider(
            "adap-2",
            Exception("unused"),
            stream_blocks=[InternalResponseBlock(type=ContentBlockType.TEXT, text="Ok")],
        )
        member2 = PoolMember("p2", "P2", adapter2)
        pool.register_provider(member2)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=2)

        req = InternalRequest(model="m", messages=[], max_tokens=10)

        blocks = []
        with pytest.raises(RouteFlowError) as exc_info:
            async for block in router.route_stream(req):
                blocks.append(block)

        assert exc_info.value.error_type == ErrorType.PROVIDER_ERROR
        assert exc_info.value.message == "Mid-stream disconnect"

        assert len(blocks) == 1
        assert blocks[0].text == "First block"
        # No failover to provider 2 should occur
        assert adapter2.stream_called_count == 0
        # Provider 1 is recorded as a failure
        assert member1.recent_failure_count == 1

    @pytest.mark.asyncio
    async def test_stream_client_cancellation_decrements_load(self) -> None:
        pool = ProviderPool()

        # Provider yielding multiple blocks
        blocks_data = [
            InternalResponseBlock(type=ContentBlockType.TEXT, text="Chunk 1"),
            InternalResponseBlock(type=ContentBlockType.TEXT, text="Chunk 2"),
        ]
        adapter = MockTestProvider("adap-1", Exception("unused"), stream_blocks=blocks_data)
        member = PoolMember("p1", "P1", adapter)
        pool.register_provider(member)

        scheduler = Scheduler(mode="health-first")
        router = RuntimeRouter(pool, scheduler, max_retries=2)
        req = InternalRequest(model="m", messages=[], max_tokens=10)

        # Call route_stream and get the async iterator
        stream_gen = router.route_stream(req)
        iterator = stream_gen.__aiter__()

        # Fetch first block (completes connection & yields first_block)
        first = await iterator.__anext__()
        assert first.text == "Chunk 1"

        # Active requests is incremented
        assert member.active_requests == 1

        # Simulate client cancel / disconnect by closing the generator
        await stream_gen.aclose()

        # Verify that GeneratorExit triggered cleanup and active_requests is decremented
        assert member.active_requests == 0
