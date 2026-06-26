"""AEGIS runtime health — Evaluates health state changes and cooldown boundaries.

Follows ARCHITECTURE.md §9, retry rules, and cooldown rules.
- Health state changes occur reactively through runtime execution events.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from aegis.providers.pool import PoolMember


def handle_provider_success(member: PoolMember) -> None:
    """Record a successful response on the pool member, restoring its health status."""
    member.recent_failure_count = 0
    member.healthy = True
    member.cooldown_expiry = None
    member.last_success = datetime.now()


def handle_provider_failure(
    member: PoolMember,
    cooldown_duration_seconds: int = 30,
    failure_threshold: int = 3,
) -> None:
    """Record a failure on the pool member, initiating cooldown if failure count is exceeded."""
    member.recent_failure_count += 1
    member.last_failure = datetime.now()

    if member.recent_failure_count >= failure_threshold:
        member.healthy = False
        member.cooldown_expiry = datetime.now() + timedelta(
            seconds=cooldown_duration_seconds
        )
