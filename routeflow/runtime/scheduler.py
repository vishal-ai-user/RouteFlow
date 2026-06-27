"""RouteFlow runtime scheduler — Selection strategies for provider pool routing.

Follows ARCHITECTURE.md §8 and scheduler rules:
- Completely stateless.
- Chooses a provider from a list of eligible members.
- Does not run HTTP calls or talk to gateway/FastAPI.
"""

from __future__ import annotations

from routeflow.core.errors import RouteFlowError, ErrorType
from routeflow.providers.pool import PoolMember


class Scheduler:
    """Selects an LLM provider from a list of eligible pool members."""
    _round_robin_counter = 0
    _last_selection_time = 0.0
    _last_selected_member = None

    def __init__(self, mode: str = "health-first") -> None:
        """Initialize the scheduler.

        Args:
            mode: The routing strategy: 'least-busy', 'health-first', 'round-robin'.
        """
        self.mode = mode.lower()

    def select(self, eligible_members: list[PoolMember]) -> PoolMember:
        """Select a member from a list of eligible pool members.

        Raises RouteFlowError if the list is empty.
        """
        if not eligible_members:
            raise RouteFlowError(
                ErrorType.PROVIDER_ERROR,
                "No eligible providers available for request.",
            )

        if self.mode == "least-busy":
            return self._select_least_busy(eligible_members)
        elif self.mode == "round-robin":
            return self._select_round_robin(eligible_members)

        # Default is health-first
        return self._select_health_first(eligible_members)

    def _select_least_busy(self, eligible_members: list[PoolMember]) -> PoolMember:
        """Select the member with the lowest active requests."""
        # Sort by active requests ascending
        sorted_members = sorted(eligible_members, key=lambda m: m.active_requests)
        return sorted_members[0]

    def _select_health_first(self, eligible_members: list[PoolMember]) -> PoolMember:
        """Prioritize healthy members with the lowest load, falling back to unhealthy."""
        # Split into healthy and unhealthy
        healthy_members = [m for m in eligible_members if m.healthy]

        if healthy_members:
            # Sort healthy ones by active requests ascending
            sorted_healthy = sorted(healthy_members, key=lambda m: m.active_requests)
            return sorted_healthy[0]

        # Fallback: choose the one with the lowest failure count and load
        sorted_all = sorted(
            eligible_members,
            key=lambda m: (m.recent_failure_count, m.active_requests),
        )
        return sorted_all[0]

    def _select_round_robin(self, eligible_members: list[PoolMember]) -> PoolMember:
        """Select members in a round-robin fashion with a 2-second stickiness window.

        This ensures concurrent/sequential sub-requests from the same client action
        (e.g., tool execution steps in a single user turn) route to the same key.
        """
        import time
        now = time.time()
        sorted_members = sorted(eligible_members, key=lambda m: m.provider_id)

        # If we selected a member recently (within 2 seconds) and it is still eligible, reuse it
        if (
            Scheduler._last_selected_member is not None
            and (now - Scheduler._last_selection_time) < 2.0
        ):
            for m in sorted_members:
                if m.provider_id == Scheduler._last_selected_member.provider_id:
                    Scheduler._last_selection_time = now
                    return m

        # Otherwise, proceed to the next provider in round-robin order
        idx = Scheduler._round_robin_counter % len(sorted_members)
        Scheduler._round_robin_counter += 1

        selected = sorted_members[idx]
        Scheduler._last_selected_member = selected
        Scheduler._last_selection_time = now
        return selected
