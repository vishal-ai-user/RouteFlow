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
from aegis.core.errors import AegisError, ErrorType
from aegis.core.logging import get_logger, request_id_var
from aegis.translator import translate_request

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["messages"], dependencies=[Depends(require_auth)])


@router.post("/messages")
async def create_message(request: CreateMessageRequest) -> dict:
    """Create a message (Claude Code-compatible).

    Validates the request payload, translates it into the internal model,
    and — once the provider pipeline is ready — forwards it through the
    runtime → provider → streaming chain.

    In Milestone 3, returns a structured error indicating the pipeline is
    not yet configured. This proves auth + validation + translation work
    end to end.
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

    # The runtime/provider pipeline will be connected in Milestones 4–6.
    raise AegisError(
        ErrorType.PROVIDER_ERROR,
        "Provider pipeline is not configured. "
        "The NVIDIA provider adapter will be available after Milestone 4.",
    )


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

