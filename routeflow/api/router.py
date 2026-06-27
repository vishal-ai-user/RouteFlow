"""RouteFlow API router — Main router that aggregates all sub-routers.

This module is the single aggregation point for all API routes.
Each domain (health, messages, etc.) defines its own APIRouter,
and this module includes them into a unified router.
"""

from fastapi import APIRouter

from routeflow.api.control_center import router as control_center_router
from routeflow.api.health import router as health_router
from routeflow.api.messages import router as messages_router

router = APIRouter()

# --- Health & status ---
router.include_router(health_router)

# --- Claude-compatible gateway ---
router.include_router(messages_router)

# --- Control Center API ---
router.include_router(control_center_router)
