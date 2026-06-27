"""RouteFlow main — FastAPI application entry point.

Startup and shutdown follow STARTUP_AND_SHUTDOWN_FLOW.md:
1. Load environment variables
2. Load settings and validate config
3. Initialize logging
4. Register routes and error handlers
5. Start server

Shutdown:
1. Log shutdown message
2. (Future milestones: flush state, close DB, drain streams)
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from routeflow import __version__
from routeflow.api.middleware import RequestIdMiddleware
from routeflow.api.router import router as api_router
from routeflow.config.settings import get_settings
from routeflow.core.errors import RouteFlowError, generic_error_handler, routeflow_error_handler
from routeflow.core.logging import get_logger, setup_logging

logger = get_logger(__name__)

# Track application startup time for uptime statistics
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler for startup and shutdown."""
    # --- Startup ---
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info("RouteFlow v%s starting", __version__)
    logger.info("Host: %s, Port: %s", settings.host, settings.port)
    logger.info("Log level: %s", settings.log_level)
    logger.info("Scheduler mode: %s", settings.scheduler_mode)
    logger.info("Streaming enabled: %s", settings.streaming_enabled)

    # Initialize SQLite database
    from routeflow.persistence.migrations import run_migrations

    try:
        run_migrations()
    except Exception as e:
        logger.critical("Database migrations failed to run at startup: %s", str(e))
        raise e

    yield

    # --- Shutdown ---
    logger.info("RouteFlow shutting down")


def create_app() -> FastAPI:
    """Create and configure the RouteFlow FastAPI application."""
    app = FastAPI(
        title="RouteFlow",
        description="Intelligent AI Gateway",
        version=__version__,
        lifespan=lifespan,
    )

    # Register middleware.
    app.add_middleware(RequestIdMiddleware)

    # Register error handlers.
    app.add_exception_handler(RouteFlowError, routeflow_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)  # type: ignore[arg-type]

    # Include API routes.
    app.include_router(api_router)

    # Redirect root to UI
    from fastapi.responses import RedirectResponse

    @app.get("/")
    async def redirect_to_ui() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    # Serve static UI files
    import os

    from fastapi.staticfiles import StaticFiles

    ui_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
    app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app


# Application instance for uvicorn.
app = create_app()


def run() -> None:
    """Run the server directly via ``python -m routeflow.main`` or the ``aegis`` CLI entry point."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "routeflow.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
