"""AEGIS health endpoints — Liveness and status checks.

Endpoints:
    GET /health  — server liveness (API_SPEC.md §4.1)
    GET /status  — server + pool summary (API_SPEC.md §4.2)

/health is always public (STARTUP_AND_SHUTDOWN_FLOW.md §5).
/status requires authentication (SECURITY.md §4).
"""

from fastapi import APIRouter, Depends

from aegis.auth.guards import require_auth

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Return server liveness.

    This endpoint is intentionally unauthenticated so that load balancers
    and monitoring tools can probe it without credentials.
    """
    return {
        "ok": True,
        "service": "aegis",
        "version": "v1",
    }


@router.get("/status", dependencies=[Depends(require_auth)])
async def status() -> dict:
    """Return server status with pool summary.

    Requires authentication since it exposes operational state.
    Pool and runtime data are placeholders until later milestones.
    """
    return {
        "ok": True,
        "service": "aegis",
        "version": "v1",
        "pool": {
            "total": 0,
            "healthy": 0,
            "disabled": 0,
        },
        "runtime": {
            "streaming": True,
            "scheduler": "health-first",
        },
    }
