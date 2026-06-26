"""AEGIS runtime scheduler — Selection strategies for provider pool routing.

Follows ARCHITECTURE.md §8 and scheduler rules:
- Completely stateless.
- Chooses a provider from a list of eligible members.
- Does not run HTTP calls or talk to gateway/FastAPI.
"""

from __future__ import annotations

from aegis.core.errors import AegisError, ErrorType
from aegis.providers.pool import PoolMember


class Scheduler:
    """Selects an LLM provider from a list of eligible pool members."""

    def __init__(self, mode: str = "health-first") -> None:
        """Initialize the scheduler.

        Args:
            mode: The routing strategy: 'least-busy', 'health-first'.
        """
        self.mode = mode.lower()

    def select(self, eligible_members: list[PoolMember]) -> PoolMember:
        """Select a member from a list of eligible pool members.

        Raises AegisError if the list is empty.
        """
        if not eligible_members:
            raise AegisError(
                ErrorType.PROVIDER_ERROR,
                "No eligible providers available for request.",
            )

        if self.mode == "least-busy":
            return self._select_least_busy(eligible_members)

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
