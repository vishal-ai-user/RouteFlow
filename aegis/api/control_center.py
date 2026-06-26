"""AEGIS Control Center API — Backend routes for administrative control and monitoring.

All routes are prefixed under `/api` and protected by `require_auth`.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from aegis import __version__
from aegis.auth.guards import require_auth
from aegis.config.settings import get_settings
from aegis.core.errors import AegisError
from aegis.core.schemas import (
    ContentBlockType,
    InternalContentBlock,
    InternalMessage,
    InternalRequest,
)
from aegis.persistence.repositories import (
    LogRepository,
    ModelMappingRepository,
    ProviderRecordRepository,
    SettingsRepository,
)
from aegis.providers.nvidia import NvidiaProvider
from aegis.providers.pool import PoolMember, get_global_pool

router = APIRouter(tags=["control-center"])


def _get_uptime_seconds() -> float:
    try:
        from aegis.main import START_TIME

        return time.time() - START_TIME
    except ImportError:
        return 0.0


def mask_api_key(key: str) -> str:
    """Mask decrypted API key to avoid leakage while providing helpful context."""
    if not key:
        return ""
    if len(key) <= 8:
        return "..."
    if key.startswith("nvapi-"):
        return f"nvapi-...{key[-4:]}"
    return f"{key[:4]}...{key[-4:]}"


# ===========================================================================
# Pydantic Schemas
# ===========================================================================


class SettingsUpdatePayload(BaseModel):
    default_model: str | None = None
    scheduler_mode: str | None = None
    retry_count: int | None = Field(None, ge=0)
    timeout_seconds: int | None = Field(None, gt=0)
    streaming_enabled: bool | None = None
    thinking_enabled: bool | None = None
    max_request_size_mb: int | None = Field(None, gt=0)
    host: str | None = None
    port: int | None = Field(None, gt=0)
    log_level: str | None = None


class ProviderCreatePayload(BaseModel):
    provider_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    base_url: str = Field(..., min_length=1)
    enabled: bool = True


class ProviderUpdatePayload(BaseModel):
    display_name: str | None = Field(None, min_length=1)
    api_key: str | None = Field(None, min_length=1)
    base_url: str | None = Field(None, min_length=1)
    enabled: bool | None = None


class ModelMappingPayload(BaseModel):
    logical_model: str = Field(..., min_length=1)
    nvidia_model: str = Field(..., min_length=1)


class ModelMappingUpdatePayload(BaseModel):
    nvidia_model: str = Field(..., min_length=1)


# ===========================================================================
# Dashboard endpoints
# ===========================================================================


@router.get("/api/dashboard/summary", dependencies=[Depends(require_auth)])
async def get_dashboard_summary() -> dict[str, Any]:
    """Retrieve high-level server health, pool metrics, and runtime statistics."""
    pool = get_global_pool()
    settings = get_settings()
    log_repo = LogRepository()

    total_requests, total_errors = await log_repo.get_total_requests_and_errors()
    success_rate = (
        100.0
        if total_requests == 0
        else round(((total_requests - total_errors) / total_requests) * 100, 2)
    )

    # Compute provider pool counts
    total_members = len(pool._members)
    healthy_members = sum(1 for m in pool._members.values() if m.healthy)
    disabled_members = sum(1 for m in pool._members.values() if not m.enabled)
    active_members = sum(1 for m in pool._members.values() if m.active_requests > 0)

    return {
        "server": {
            "status": "running",
            "version": __version__,
            "uptime_seconds": _get_uptime_seconds(),
        },
        "pool": {
            "total_members": total_members,
            "healthy_members": healthy_members,
            "disabled_members": disabled_members,
            "active_members": active_members,
        },
        "runtime": {
            "scheduler_mode": settings.scheduler_mode,
            "streaming_enabled": settings.streaming_enabled,
            "total_requests": total_requests,
            "total_errors": total_errors,
            "success_rate": success_rate,
        },
    }


@router.get("/api/control/health", dependencies=[Depends(require_auth)])
async def get_control_health() -> dict[str, Any]:
    """Provide detailed health monitoring data for the Control Center UI."""
    summary = await get_dashboard_summary()
    pool = get_global_pool()

    # Detail active requests and health status per provider
    providers_health = []
    for p_id, member in pool._members.items():
        providers_health.append(
            {
                "provider_id": p_id,
                "display_name": member.display_name,
                "enabled": member.enabled,
                "healthy": member.healthy,
                "active_requests": member.active_requests,
                "recent_failures": member.recent_failure_count,
                "cooldown_expiry": (
                    member.cooldown_expiry.isoformat() if member.cooldown_expiry else None
                ),
            }
        )

    return {
        **summary,
        "providers": providers_health,
        "timestamp": datetime.now().isoformat(),
    }


# ===========================================================================
# Settings endpoints
# ===========================================================================


@router.get("/api/settings", dependencies=[Depends(require_auth)])
async def list_settings() -> dict[str, Any]:
    """List current safe application settings (excluding secrets)."""
    settings = get_settings()
    return {
        "default_model": settings.default_model,
        "scheduler_mode": settings.scheduler_mode,
        "retry_count": settings.retry_count,
        "timeout_seconds": settings.timeout_seconds,
        "streaming_enabled": settings.streaming_enabled,
        "thinking_enabled": settings.thinking_enabled,
        "max_request_size_mb": settings.max_request_size_mb,
        "host": settings.host,
        "port": settings.port,
        "log_level": settings.log_level,
        "database_path": settings.database_path,
    }


@router.put("/api/settings", dependencies=[Depends(require_auth)])
async def update_settings(payload: SettingsUpdatePayload) -> dict[str, Any]:
    """Update application settings and flush the local settings cache."""
    settings_repo = SettingsRepository()

    # Exclude None values to only update provided fields
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        # Store boolean and integer values as strings in DB
        await settings_repo.set(key, str(value))

    # Invalidate cache so future get_settings() loads overrides from database
    get_settings.cache_clear()

    return await list_settings()


# ===========================================================================
# Providers endpoints
# ===========================================================================


@router.get("/api/providers", dependencies=[Depends(require_auth)])
async def list_providers() -> list[dict[str, Any]]:
    """List all registered NVIDIA provider members, with masked API keys."""
    provider_repo = ProviderRecordRepository()
    records = await provider_repo.get_all()

    result = []
    db_provider_ids = set()
    for r in records:
        db_provider_ids.add(r.provider_id)
        try:
            raw_key = provider_repo.decrypt_key(r.api_key_encrypted)
            masked_key = mask_api_key(raw_key)
        except Exception:
            masked_key = "..."

        result.append(
            {
                "id": r.id,
                "provider_id": r.provider_id,
                "display_name": r.display_name,
                "base_url": r.base_url,
                "enabled": r.enabled,
                "api_key": masked_key,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
        )

    # Append environment-bootstrapped providers from global pool if not in database
    pool = get_global_pool()
    for p_id, member in pool._members.items():
        if p_id not in db_provider_ids:
            raw_key = member.provider.api_key or ""
            masked_key = mask_api_key(raw_key)
            result.append(
                {
                    "id": 0,
                    "provider_id": p_id,
                    "display_name": member.display_name,
                    "base_url": member.provider.base_url,
                    "enabled": member.enabled,
                    "api_key": masked_key,
                    "created_at": "",
                    "updated_at": "",
                }
            )

    return result


@router.post(
    "/api/providers", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)]
)
async def create_provider(payload: ProviderCreatePayload) -> dict[str, Any]:
    """Register a new provider. Encrypts its API key in the DB and syncs the pool."""
    provider_repo = ProviderRecordRepository()

    existing = await provider_repo.get(payload.provider_id)
    pool = get_global_pool()
    if existing or payload.provider_id in pool._members:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider with ID '{payload.provider_id}' already exists.",
        )

    # 1. Create in database (which performs encryption)
    record = await provider_repo.create(
        provider_id=payload.provider_id,
        display_name=payload.display_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        enabled=payload.enabled,
    )

    # 2. Register/sync in-memory global pool
    pool = get_global_pool()
    settings = get_settings()

    provider_obj = NvidiaProvider(
        name=payload.display_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        timeout_seconds=float(settings.timeout_seconds),
    )
    member = PoolMember(
        provider_id=payload.provider_id,
        display_name=payload.display_name,
        provider=provider_obj,
        enabled=payload.enabled,
    )
    pool.register_provider(member)

    return {
        "id": record.id,
        "provider_id": record.provider_id,
        "display_name": record.display_name,
        "base_url": record.base_url,
        "enabled": record.enabled,
        "api_key": mask_api_key(payload.api_key),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.put("/api/providers/{provider_id}", dependencies=[Depends(require_auth)])
async def update_provider(provider_id: str, payload: ProviderUpdatePayload) -> dict[str, Any]:
    """Update fields on an existing provider, syncing to the database and in-memory pool."""
    pool = get_global_pool()
    member = pool.get_provider(provider_id)

    provider_repo = ProviderRecordRepository()
    existing = await provider_repo.get(provider_id)

    if not existing and not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )

    if not existing and member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider '{provider_id}' is configured via the environment "
                "and cannot be modified."
            ),
        )

    # Update in DB
    await provider_repo.update(
        provider_id=provider_id,
        display_name=payload.display_name,
        api_key=payload.api_key,
        base_url=payload.base_url,
        enabled=payload.enabled,
    )

    # Sync with in-memory pool
    if member:
        if payload.display_name is not None:
            member.display_name = payload.display_name
            member.provider.name = payload.display_name
        if payload.api_key is not None:
            member.provider.api_key = payload.api_key
        if payload.base_url is not None:
            member.provider.base_url = payload.base_url
        if payload.enabled is not None:
            member.enabled = payload.enabled

    updated_rec = await provider_repo.get(provider_id)
    raw_key = provider_repo.decrypt_key(updated_rec.api_key_encrypted) if updated_rec else ""

    return {
        "id": updated_rec.id,
        "provider_id": updated_rec.provider_id,
        "display_name": updated_rec.display_name,
        "base_url": updated_rec.base_url,
        "enabled": updated_rec.enabled,
        "api_key": mask_api_key(raw_key),
        "created_at": updated_rec.created_at,
        "updated_at": updated_rec.updated_at,
    }


@router.delete("/api/providers/{provider_id}", dependencies=[Depends(require_auth)])
async def delete_provider(provider_id: str) -> dict[str, bool]:
    """Remove a provider member from the database and the active pool."""
    pool = get_global_pool()
    member = pool.get_provider(provider_id)

    provider_repo = ProviderRecordRepository()
    existing = await provider_repo.get(provider_id)

    if not existing and not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )

    if not existing and member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Provider '{provider_id}' is configured via the environment and cannot be deleted."
            ),
        )

    await provider_repo.delete(provider_id)
    pool.remove_provider(provider_id)

    return {"ok": True}


@router.post("/api/providers/{provider_id}/enable", dependencies=[Depends(require_auth)])
async def enable_provider(provider_id: str) -> dict[str, Any]:
    """Mark a provider enabled in both DB and runtime pool."""
    pool = get_global_pool()
    member = pool.get_provider(provider_id)

    provider_repo = ProviderRecordRepository()
    existing = await provider_repo.get(provider_id)

    if not existing and not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )

    if existing:
        await provider_repo.update(provider_id=provider_id, enabled=True)

    pool.enable_provider(provider_id)

    raw_key = ""
    if existing:
        updated_rec = await provider_repo.get(provider_id)
        raw_key = provider_repo.decrypt_key(updated_rec.api_key_encrypted) if updated_rec else ""
    elif member:
        raw_key = member.provider.api_key or ""

    return {
        "provider_id": provider_id,
        "enabled": True,
        "api_key": mask_api_key(raw_key),
    }


@router.post("/api/providers/{provider_id}/disable", dependencies=[Depends(require_auth)])
async def disable_provider(provider_id: str) -> dict[str, Any]:
    """Mark a provider disabled in both DB and runtime pool."""
    pool = get_global_pool()
    member = pool.get_provider(provider_id)

    provider_repo = ProviderRecordRepository()
    existing = await provider_repo.get(provider_id)

    if not existing and not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found.",
        )

    if existing:
        await provider_repo.update(provider_id=provider_id, enabled=False)

    pool.disable_provider(provider_id)

    raw_key = ""
    if existing:
        updated_rec = await provider_repo.get(provider_id)
        raw_key = provider_repo.decrypt_key(updated_rec.api_key_encrypted) if updated_rec else ""
    elif member:
        raw_key = member.provider.api_key or ""

    return {
        "provider_id": provider_id,
        "enabled": False,
        "api_key": mask_api_key(raw_key),
    }


@router.post("/api/providers/{provider_id}/test", dependencies=[Depends(require_auth)])
async def test_provider_connection(provider_id: str) -> dict[str, Any]:
    """Run a small completion request against a provider to test its credentials."""
    pool = get_global_pool()
    member = pool.get_provider(provider_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' is not loaded in the active pool.",
        )

    test_req = InternalRequest(
        model="test-ping",
        messages=[
            InternalMessage(
                role="user",
                content=[InternalContentBlock(type=ContentBlockType.TEXT, text="ping")],
            )
        ],
        max_tokens=1,
    )

    try:
        start = time.perf_counter()
        await member.provider.complete(test_req)
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "message": "Connection test successful.",
            "latency_ms": latency,
        }
    except AegisError as exc:
        return {
            "ok": False,
            "error_type": exc.error_type.value,
            "error_message": exc.message,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error_type": "unexpected_error",
            "error_message": str(exc),
        }


# ===========================================================================
# Model Mappings endpoints
# ===========================================================================


@router.get("/api/model_mappings", dependencies=[Depends(require_auth)])
async def list_model_mappings() -> list[dict[str, Any]]:
    """List all logical model mappings."""
    mapping_repo = ModelMappingRepository()
    records = await mapping_repo.get_all()
    return [
        {
            "id": r.id,
            "logical_model": r.logical_model,
            "nvidia_model": r.nvidia_model,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in records
    ]


@router.post(
    "/api/model_mappings", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_auth)]
)
async def create_model_mapping(payload: ModelMappingPayload) -> dict[str, Any]:
    """Create or overwrite a logical-to-NVIDIA model mapping."""
    mapping_repo = ModelMappingRepository()
    record = await mapping_repo.create(
        logical_model=payload.logical_model,
        nvidia_model=payload.nvidia_model,
    )
    return {
        "id": record.id,
        "logical_model": record.logical_model,
        "nvidia_model": record.nvidia_model,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@router.put("/api/model_mappings/{logical_model}", dependencies=[Depends(require_auth)])
async def update_model_mapping(
    logical_model: str, payload: ModelMappingUpdatePayload
) -> dict[str, Any]:
    """Update target NVIDIA model for an existing logical model."""
    mapping_repo = ModelMappingRepository()

    existing = await mapping_repo.get_nvidia_model(logical_model)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping for logical model '{logical_model}' not found.",
        )

    await mapping_repo.update(
        logical_model=logical_model,
        nvidia_model=payload.nvidia_model,
    )

    records = await mapping_repo.get_all()
    updated_rec = next((r for r in records if r.logical_model == logical_model), None)

    if not updated_rec:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve updated mapping.",
        )

    return {
        "id": updated_rec.id,
        "logical_model": updated_rec.logical_model,
        "nvidia_model": updated_rec.nvidia_model,
        "created_at": updated_rec.created_at,
        "updated_at": updated_rec.updated_at,
    }


@router.delete("/api/model_mappings/{logical_model}", dependencies=[Depends(require_auth)])
async def delete_model_mapping(logical_model: str) -> dict[str, bool]:
    """Delete a logical model mapping."""
    mapping_repo = ModelMappingRepository()

    existing = await mapping_repo.get_nvidia_model(logical_model)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping for logical model '{logical_model}' not found.",
        )

    await mapping_repo.delete(logical_model)
    return {"ok": True}


# ===========================================================================
# Logs endpoints
# ===========================================================================


@router.get("/api/logs/requests", dependencies=[Depends(require_auth)])
async def get_paginated_requests(
    limit: int = 20,
    offset: int = 0,
    provider_id: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve paginated request logs history with optional filters."""
    log_repo = LogRepository()
    records = await log_repo.get_paginated_requests(
        limit=limit,
        offset=offset,
        provider_id=provider_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        {
            "id": r.id,
            "request_id": r.request_id,
            "model": r.model,
            "stream": r.stream,
            "provider_id": r.provider_id,
            "status_code": r.status_code,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at,
        }
        for r in records
    ]


@router.get("/api/logs/requests/{request_id}", dependencies=[Depends(require_auth)])
async def get_request_details(request_id: str) -> dict[str, Any]:
    """Retrieve the full lifecycle details (request, response, error, usage) for a request."""
    log_repo = LogRepository()

    # 1. Fetch main request log using the repository method
    req = await log_repo.get_request_log(request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request log with ID '{request_id}' not found.",
        )

    req_dict = {
        "id": req.id,
        "request_id": req.request_id,
        "model": req.model,
        "stream": req.stream,
        "provider_id": req.provider_id,
        "status_code": req.status_code,
        "latency_ms": req.latency_ms,
        "created_at": req.created_at,
    }

    # 2. Fetch response details
    resp_log = await log_repo.get_response_log(request_id)
    # 3. Fetch error details
    err_log = await log_repo.get_error_log(request_id)
    # 4. Fetch usage details
    usage_entry = await log_repo.get_usage_entry(request_id)

    return {
        "request": req_dict,
        "response": {
            "content": resp_log.content if resp_log else None,
            "stop_reason": resp_log.stop_reason if resp_log else None,
            "created_at": resp_log.created_at if resp_log else None,
        }
        if resp_log
        else None,
        "error": {
            "error_type": err_log.error_type if err_log else None,
            "error_message": err_log.error_message if err_log else None,
            "created_at": err_log.created_at if err_log else None,
        }
        if err_log
        else None,
        "usage": {
            "input_tokens": usage_entry.input_tokens if usage_entry else 0,
            "output_tokens": usage_entry.output_tokens if usage_entry else 0,
            "total_tokens": usage_entry.total_tokens if usage_entry else 0,
            "created_at": usage_entry.created_at if usage_entry else None,
        }
        if usage_entry
        else None,
    }


@router.get("/api/logs/errors", dependencies=[Depends(require_auth)])
async def get_paginated_errors(
    limit: int = 20,
    offset: int = 0,
    error_type: str | None = None,
    provider_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve paginated error logs with optional filters."""
    log_repo = LogRepository()
    records = await log_repo.get_paginated_errors(
        limit=limit,
        offset=offset,
        error_type=error_type,
        provider_id=provider_id,
        start_date=start_date,
        end_date=end_date,
    )
    return records


@router.get("/api/logs", dependencies=[Depends(require_auth)])
async def get_combined_logs(
    limit: int = 20,
    offset: int = 0,
    provider_id: str | None = None,
    request_id: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """Retrieve recent request and error logs combined (compatibility endpoint)."""
    log_repo = LogRepository()

    if request_id:
        # Check single request details
        req = await log_repo.get_request_log(request_id)
        requests = []
        if req:
            requests.append(
                {
                    "id": req.id,
                    "request_id": req.request_id,
                    "model": req.model,
                    "stream": req.stream,
                    "provider_id": req.provider_id,
                    "status_code": req.status_code,
                    "latency_ms": req.latency_ms,
                    "created_at": req.created_at,
                }
            )

        errors = []
        if req:
            err = await log_repo.get_error_log(request_id)
            if err:
                errors.append(
                    {
                        "id": err.id,
                        "request_id": err.request_id,
                        "error_type": err.error_type,
                        "error_message": err.error_message,
                        "created_at": err.created_at,
                        "provider_id": req.provider_id,
                        "model": req.model,
                    }
                )
    else:
        req_logs = await log_repo.get_paginated_requests(
            limit=limit, offset=offset, provider_id=provider_id
        )
        requests = [
            {
                "id": r.id,
                "request_id": r.request_id,
                "model": r.model,
                "stream": r.stream,
                "provider_id": r.provider_id,
                "status_code": r.status_code,
                "latency_ms": r.latency_ms,
                "created_at": r.created_at,
            }
            for r in req_logs
        ]

        # If severity is 'error', filter for requests that failed
        if severity == "error":
            requests = [r for r in requests if r["status_code"] is None or r["status_code"] >= 400]

        errors = await log_repo.get_paginated_errors(
            limit=limit, offset=offset, provider_id=provider_id
        )

    return {
        "requests": requests,
        "errors": errors,
    }


# ===========================================================================
# Usage endpoints
# ===========================================================================


@router.get("/api/usage/summary", dependencies=[Depends(require_auth)])
async def get_usage_summary() -> dict[str, Any]:
    """Retrieve token usage summaries grouped by day, provider, and model."""
    log_repo = LogRepository()
    summary = await log_repo.get_usage_summary()
    return summary
