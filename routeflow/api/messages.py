"""RouteFlow message endpoints — Claude Code-compatible gateway routes.

Endpoints:
    POST /v1/messages            — Main chat endpoint (API_SPEC.md §4.5)
    POST /v1/messages/count_tokens — Token estimation (API_SPEC.md §4.4)
    GET  /v1/models              — Available models (API_SPEC.md §4.3)

All endpoints require authentication (SECURITY.md §4).

The gateway validates requests and passes them through the translator
(Milestone 3). The runtime, provider, and streaming layers will be
wired in subsequent milestones.
"""

import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends

from routeflow.api.models import (
    CountTokensRequest,
    CountTokensResponse,
    CreateMessageRequest,
    ModelInfo,
    ModelsResponse,
)
from routeflow.auth.guards import require_auth
from routeflow.config.settings import get_settings
from routeflow.core.errors import RouteFlowError
from routeflow.core.logging import get_logger, request_id_var
from routeflow.providers.pool import get_global_pool
from routeflow.runtime.router import RuntimeRouter
from routeflow.runtime.scheduler import Scheduler
from routeflow.stream.sse import sse_streaming_response
from routeflow.translator import translate_request, translate_response

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

    import os

    from routeflow.core.logging import request_origin_var
    if "PYTEST_CURRENT_TEST" in os.environ:
        request_origin_var.set("Unit test")
    else:
        request_origin_var.set("Claude Code")

    # Translate the gateway request into an internal request.
    request_id = request_id_var.get() or f"req_{uuid.uuid4().hex[:16]}"
    internal_request = translate_request(request, request_id=request_id)

    logger.info(
        "Translated request: model=%s, messages=%d, system_blocks=%d, stream=%s",
        internal_request.model,
        len(internal_request.messages),
        len(internal_request.system),
        internal_request.stream,
    )

    # Initialize persistence repository
    from routeflow.persistence.repositories import LogRepository

    log_repo = LogRepository()

    # Log incoming request metadata in DB
    await log_repo.log_request(request_id=request_id, model=request.model, stream=request.stream)
    start_time = time.perf_counter()

    # Initialize pool, scheduler, and runtime router
    pool = get_global_pool()
    settings = get_settings()
    scheduler = Scheduler(mode=settings.scheduler_mode)
    router_instance = RuntimeRouter(
        pool=pool,
        scheduler=scheduler,
        max_retries=settings.retry_count,
        cooldown_duration_seconds=5,
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

        # Define logging stream wrapper to intercept tokens, responses, and errors
        async def logging_stream_wrapper(iterator):
            accumulated_text = []
            stop_reason = "end_turn"
            output_tokens = 0
            error_occurred = False
            completed = False
            try:
                async for block in iterator:
                    from routeflow.core.schemas import ContentBlockType

                    if block.type == ContentBlockType.TEXT and block.text:
                        accumulated_text.append(block.text)
                        output_tokens += max(1, len(block.text) // 4)
                    elif block.type == ContentBlockType.THINKING and block.thinking_text:
                        output_tokens += max(1, len(block.thinking_text) // 4)
                    elif block.type == ContentBlockType.TOOL_USE:
                        stop_reason = "tool_use"
                        import json

                        tool_input_json = json.dumps(block.tool_input or {})
                        output_tokens += max(1, len(tool_input_json) // 4)
                    yield block
                completed = True
            except Exception as stream_exc:
                error_occurred = True
                latency = int((time.perf_counter() - start_time) * 1000)
                err_type = "provider_error"
                err_msg = str(stream_exc)
                if isinstance(stream_exc, RouteFlowError):
                    err_type = stream_exc.error_type.value
                    err_msg = stream_exc.message
                from routeflow.core.logging import provider_id_var

                provider_id = provider_id_var.get()

                async def do_error_logging():
                    try:
                        await log_repo.update_request_status(
                            request_id, status_code=500, latency_ms=latency, provider_id=provider_id
                        )
                        await log_repo.log_error(
                            request_id, error_type=err_type, error_message=err_msg
                        )
                    except Exception as le:
                        logger.error("Failed to write stream error log: %s", str(le))

                import asyncio

                asyncio.create_task(do_error_logging())
                raise stream_exc
            finally:
                if not error_occurred:
                    latency = int((time.perf_counter() - start_time) * 1000)
                    content = "".join(accumulated_text)
                    from routeflow.core.logging import provider_id_var

                    provider_id = provider_id_var.get()
                    status_code = 200 if completed else 499

                    async def do_final_logging():
                        try:
                            await log_repo.update_request_status(
                                request_id,
                                status_code=status_code,
                                latency_ms=latency,
                                provider_id=provider_id,
                            )
                            await log_repo.log_response(
                                request_id, content=content, stop_reason=stop_reason
                            )
                            await log_repo.log_usage(
                                request_id,
                                input_tokens=estimated_input_tokens,
                                output_tokens=output_tokens,
                            )
                        except Exception as le:
                            logger.error("Failed to write final stream log: %s", str(le))

                    import asyncio

                    asyncio.create_task(do_final_logging())

        wrapped_blocks = logging_stream_wrapper(blocks_iterator)

        return sse_streaming_response(
            blocks_iterator=wrapped_blocks,
            message_id=message_id,
            model=request.model,
            input_tokens=estimated_input_tokens,
        )
    else:
        try:
            # Route non-streaming request
            internal_response = await router_instance.route(internal_request)

            # Log successful response metrics
            latency = int((time.perf_counter() - start_time) * 1000)
            from routeflow.core.logging import provider_id_var

            provider_id = provider_id_var.get()
            await log_repo.update_request_status(
                request_id, status_code=200, latency_ms=latency, provider_id=provider_id
            )

            # Extract output text
            content_text = ""
            if internal_response.content:
                content_text = "".join(
                    block.text for block in internal_response.content if block.text
                )

            # Save response details and token counts
            stop_reason_val = (
                internal_response.stop_reason.value if internal_response.stop_reason else "end_turn"
            )
            await log_repo.log_response(
                request_id, content=content_text, stop_reason=stop_reason_val
            )
            await log_repo.log_usage(
                request_id,
                input_tokens=internal_response.usage.input_tokens,
                output_tokens=internal_response.usage.output_tokens,
            )

            return translate_response(internal_response)
        except Exception as exc:
            # Log error conditions
            latency = int((time.perf_counter() - start_time) * 1000)
            err_type = "provider_error"
            err_msg = str(exc)
            status_code = 502
            if isinstance(exc, RouteFlowError):
                err_type = exc.error_type.value
                err_msg = exc.message
                from routeflow.core.errors import ERROR_STATUS_CODES

                status_code = ERROR_STATUS_CODES.get(exc.error_type, 502)

            from routeflow.core.logging import provider_id_var

            provider_id = provider_id_var.get()
            await log_repo.update_request_status(
                request_id, status_code=status_code, latency_ms=latency, provider_id=provider_id
            )
            await log_repo.log_error(request_id, error_type=err_type, error_message=err_msg)
            raise exc


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
