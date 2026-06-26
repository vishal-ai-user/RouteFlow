"""AEGIS message endpoints — Claude Code-compatible gateway routes.

Endpoints:
    POST /v1/messages            — Main chat endpoint (API_SPEC.md §4.5)
    POST /v1/messages/count_tokens — Token estimation (API_SPEC.md §4.4)
    GET  /v1/models              — Available models (API_SPEC.md §4.3)

All endpoints require authentication (SECURITY.md §4).

In Milestone 2, the gateway validates requests but does not forward them
to a provider. The translator, runtime, and provider layers will be wired
in subsequent milestones. Valid requests receive a structured "pipeline not
ready" error so that auth and validation can be fully tested.
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
from aegis.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["messages"], dependencies=[Depends(require_auth)])


@router.post("/messages")
async def create_message(request: CreateMessageRequest) -> dict:
    """Create a message (Claude Code-compatible).

    Validates the request payload and — once the provider pipeline is ready —
    forwards it through the translator → runtime → provider → streaming chain.

    In Milestone 2, returns a structured error indicating the pipeline is not
    yet configured. This proves auth + validation work end to end.
    """
    logger.info(
        "Received message request: model=%s, messages=%d, stream=%s, max_tokens=%d",
        request.model,
        len(request.messages),
        request.stream,
        request.max_tokens,
    )

    # Gateway validated the request. The translator/runtime/provider pipeline
    # will be connected in Milestones 3–6.
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
