"""AEGIS message endpoints — Claude Code-compatible gateway routes.

Endpoints:
    POST /v1/messages            — Main chat endpoint (API_SPEC.md §4.5)
    POST /v1/messages/count_tokens — Token estimation (API_SPEC.md §4.4)
    GET  /v1/models              — Available models (API_SPEC.md §4.3)

All endpoints require authentication (SECURITY.md §4).

The gateway validates requests and passes them through the translator
(Milestone 3). The runtime, provider, and streaming layers will be
wired in subsequent milestones.
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from aegis.api.models import (
    CountTokensRequest,
    CountTokensResponse,
    CreateMessageRequest,
    ModelInfo,
    ModelsResponse,
)
from aegis.auth.guards import require_auth
from aegis.config.settings import get_settings
from aegis.core.logging import get_logger, request_id_var
from aegis.providers.pool import get_global_pool
from aegis.runtime.router import RuntimeRouter
from aegis.runtime.scheduler import Scheduler
from aegis.stream.sse import sse_streaming_response
from aegis.translator import translate_request, translate_response

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["messages"], dependencies=[Depends(require_auth)])


@router.post("/messages")
async def create_message(request: CreateMessageRequest) -> Any:
    """Create a message (Claude Code-compatible).

    Validates the request payload, translates it into the internal model,
    routes it through the runtime router to the selected provider,
    and returns a translated JSON payload or SSE StreamingResponse.
    """
    logger.info(
        "Received message request: model=%s, messages=%d, stream=%s, max_tokens=%d",
        request.model,
        len(request.messages),
        request.stream,
        request.max_tokens,
    )

    # Translate the gateway request into an internal request.
    request_id = request_id_var.get() or ""
    internal_request = translate_request(request, request_id=request_id)

    logger.info(
        "Translated request: model=%s, messages=%d, system_blocks=%d, stream=%s",
        internal_request.model,
        len(internal_request.messages),
        len(internal_request.system),
        internal_request.stream,
    )

    # Initialize pool, scheduler, and runtime router
    pool = get_global_pool()
    settings = get_settings()
    scheduler = Scheduler(mode=settings.scheduler_mode)
    router_instance = RuntimeRouter(
        pool=pool,
        scheduler=scheduler,
        max_retries=settings.retry_count,
        cooldown_duration_seconds=30,
    )

    # Estimate input tokens for the start event
    total_chars = 0
    if request.system:
        total_chars += len(str(request.system))
    for msg in request.messages:
        total_chars += len(str(msg.content))
    estimated_input_tokens = max(1, total_chars // 4)

    if request.stream:
        # Route streaming request
        blocks_iterator = router_instance.route_stream(internal_request)
        message_id = f"msg_{uuid.uuid4().hex[:16]}"
        return sse_streaming_response(
            blocks_iterator=blocks_iterator,
            message_id=message_id,
            model=request.model,
            input_tokens=estimated_input_tokens,
        )
    else:
        # Route non-streaming request
        internal_response = await router_instance.route(internal_request)
        return translate_response(internal_response)


@router.post("/messages/count_tokens")
async def count_tokens(request: CountTokensRequest) -> CountTokensResponse:
    """Estimate token count for the given messages.

    Uses a simple character-based heuristic for V1.
    A more accurate tokenizer can be added later.
    """
    logger.info(
        "Token count request: model=%s, messages=%d",
        request.model,
        len(request.messages),
    )

    # Simple heuristic: ~4 characters per token.
    total_chars = 0
    if request.system:
        if isinstance(request.system, str):
            total_chars += len(request.system)
        else:
            for block in request.system:
                total_chars += len(str(block))

    for msg in request.messages:
        if isinstance(msg.content, str):
            total_chars += len(msg.content)
        else:
            for block in msg.content:
                if block.text:
                    total_chars += len(block.text)

    estimated_tokens = max(1, total_chars // 4)

    return CountTokensResponse(input_tokens=estimated_tokens)


@router.get("/models")
async def list_models() -> ModelsResponse:
    """Return the models exposed by the gateway.

    V1 returns a small logical model set from configuration.
    The actual NVIDIA model mapping happens in the translator layer.
    """
    settings = get_settings()

    return ModelsResponse(
        data=[
            ModelInfo(id=settings.default_model),
        ]
    )

