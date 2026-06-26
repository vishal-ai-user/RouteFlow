"""AEGIS provider pool — In-memory registry and health tracking for pool members.

Follows ARCHITECTURE.md §9 and pool rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aegis.providers.base import BaseProvider


class PoolMember:
    """Represents a single registered provider member in the pool."""

    def __init__(
        self,
        provider_id: str,
        display_name: str,
        provider: BaseProvider,
        enabled: bool = True,
    ) -> None:
        self.provider_id = provider_id
        self.display_name = display_name
        self.provider = provider
        self.enabled = enabled

        # Runtime states
        self.healthy = True
        self.active_requests = 0
        self.last_success: datetime | None = None
        self.last_failure: datetime | None = None
        self.cooldown_expiry: datetime | None = None
        self.recent_failure_count = 0

    def is_cooling_down(self, now: datetime) -> bool:
        """Check if the member is currently in cooldown."""
        if self.cooldown_expiry is None:
            return False
        return now < self.cooldown_expiry


class ProviderPool:
    """In-memory registry and runtime manager for provider members."""

    def __init__(self) -> None:
        self._members: dict[str, PoolMember] = {}

    def register_provider(self, member: PoolMember) -> None:
        """Add a provider member to the registry."""
        self._members[member.provider_id] = member

    def remove_provider(self, provider_id: str) -> None:
        """Remove a provider member from the registry."""
        self._members.pop(provider_id, None)

    def get_provider(self, provider_id: str) -> PoolMember | None:
        """Retrieve a provider member by its identifier."""
        return self._members.get(provider_id)

    def enable_provider(self, provider_id: str) -> None:
        """Enable a registered provider."""
        member = self.get_provider(provider_id)
        if member:
            member.enabled = True

    def disable_provider(self, provider_id: str) -> None:
        """Disable a registered provider."""
        member = self.get_provider(provider_id)
        if member:
            member.enabled = False

    def mark_healthy(self, provider_id: str) -> None:
        """Set a provider's health state to True."""
        member = self.get_provider(provider_id)
        if member:
            member.healthy = True

    def mark_unhealthy(self, provider_id: str) -> None:
        """Set a provider's health state to False."""
        member = self.get_provider(provider_id)
        if member:
            member.healthy = False

    def increment_active_requests(self, provider_id: str) -> None:
        """Increment the active requests count for a provider."""
        member = self.get_provider(provider_id)
        if member:
            member.active_requests += 1

    def decrement_active_requests(self, provider_id: str) -> None:
        """Decrement the active requests count for a provider, ensuring it doesn't drop below 0."""
        member = self.get_provider(provider_id)
        if member:
            member.active_requests = max(0, member.active_requests - 1)

    def retrieve_eligible_providers(self) -> list[PoolMember]:
        """Retrieve all currently eligible pool members.

        If a member's cooldown period has expired, it is automatically
        marked healthy, failure count is reset, and it becomes eligible again.
        """
        now = datetime.now()
        eligible: list[PoolMember] = []

        for member in self._members.values():
            # 1. Skip disabled members
            if not member.enabled:
                continue

            # 2. Check and expire cooldown if time has elapsed
            if member.cooldown_expiry is not None:
                if now >= member.cooldown_expiry:
                    # Automatic recovery
                    member.cooldown_expiry = None
                    member.recent_failure_count = 0
                    member.healthy = True
                else:
                    # Still in cooldown
                    continue

            eligible.append(member)

        return eligible
