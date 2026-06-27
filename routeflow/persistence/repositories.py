"""RouteFlow database repositories — Typed database access methods.

Executes blocking sqlite3 queries in thread pools to keep async code non-blocking.
Follows ARCHITECTURE.md §10 and security rules.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from routeflow.persistence.db import (
    decrypt_val,
    encrypt_val,
    get_db_connection,
    get_encryption_key,
)
from routeflow.persistence.models import (
    ErrorLog,
    ModelMapping,
    ProviderRecord,
    RequestLog,
    ResponseLog,
    Setting,
    UsageEntry,
)


class SettingsRepository:
    """Repository for global application settings storage."""

    @staticmethod
    def _get_sync(key: str, db_path: str | None) -> Setting | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, updated_at FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return None
            return Setting(key=row["key"], value=row["value"], updated_at=row["updated_at"])

    async def get(self, key: str, db_path: str | None = None) -> Setting | None:
        """Retrieve a setting by key."""
        return await asyncio.to_thread(self._get_sync, key, db_path)

    @staticmethod
    def _set_sync(key: str, value: str, db_path: str | None) -> None:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    async def set(self, key: str, value: str, db_path: str | None = None) -> None:
        """Create or update a setting key-value pair."""
        await asyncio.to_thread(self._set_sync, key, value, db_path)

    @staticmethod
    def _get_all_sync(db_path: str | None) -> dict[str, str]:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            return {row["key"]: row["value"] for row in rows}

    async def get_all(self, db_path: str | None = None) -> dict[str, str]:
        """Retrieve all setting key-value pairs as a dictionary."""
        return await asyncio.to_thread(self._get_all_sync, db_path)


class ProviderRecordRepository:
    """Repository for NVIDIA provider configuration records."""

    @staticmethod
    def _create_sync(
        provider_id: str,
        display_name: str,
        api_key: str,
        base_url: str,
        enabled: bool,
        db_path: str | None,
    ) -> ProviderRecord:
        now = datetime.now().isoformat()
        encryption_key = get_encryption_key()
        api_key_encrypted = encrypt_val(api_key, encryption_key)

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO provider_records (
                    provider_id, display_name, api_key_encrypted,
                    base_url, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    display_name,
                    api_key_encrypted,
                    base_url,
                    1 if enabled else 0,
                    now,
                    now,
                ),
            )
            row_id = cursor.lastrowid
            return ProviderRecord(
                id=row_id,
                provider_id=provider_id,
                display_name=display_name,
                api_key_encrypted=api_key_encrypted,
                base_url=base_url,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )

    async def create(
        self,
        provider_id: str,
        display_name: str,
        api_key: str,
        base_url: str,
        enabled: bool = True,
        db_path: str | None = None,
    ) -> ProviderRecord:
        """Create a new provider record in the database."""
        return await asyncio.to_thread(
            self._create_sync, provider_id, display_name, api_key, base_url, enabled, db_path
        )

    @staticmethod
    def _get_sync(provider_id: str, db_path: str | None) -> ProviderRecord | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, provider_id, display_name, api_key_encrypted,
                       base_url, enabled, created_at, updated_at
                FROM provider_records
                WHERE provider_id = ?
                """,
                (provider_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ProviderRecord(
                id=row["id"],
                provider_id=row["provider_id"],
                display_name=row["display_name"],
                api_key_encrypted=row["api_key_encrypted"],
                base_url=row["base_url"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    async def get(self, provider_id: str, db_path: str | None = None) -> ProviderRecord | None:
        """Retrieve a provider record by provider_id."""
        return await asyncio.to_thread(self._get_sync, provider_id, db_path)

    @staticmethod
    def _get_all_sync(db_path: str | None) -> list[ProviderRecord]:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, provider_id, display_name, api_key_encrypted,
                       base_url, enabled, created_at, updated_at
                FROM provider_records
                """
            )
            rows = cursor.fetchall()
            return [
                ProviderRecord(
                    id=row["id"],
                    provider_id=row["provider_id"],
                    display_name=row["display_name"],
                    api_key_encrypted=row["api_key_encrypted"],
                    base_url=row["base_url"],
                    enabled=bool(row["enabled"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    async def get_all(self, db_path: str | None = None) -> list[ProviderRecord]:
        """Retrieve all registered provider records."""
        return await asyncio.to_thread(self._get_all_sync, db_path)

    @staticmethod
    def _update_sync(
        provider_id: str,
        display_name: str | None,
        api_key: str | None,
        base_url: str | None,
        enabled: bool | None,
        db_path: str | None,
    ) -> None:
        now = datetime.now().isoformat()
        updates = []
        params = []

        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if api_key is not None:
            encryption_key = get_encryption_key()
            api_key_encrypted = encrypt_val(api_key, encryption_key)
            updates.append("api_key_encrypted = ?")
            params.append(api_key_encrypted)
        if base_url is not None:
            updates.append("base_url = ?")
            params.append(base_url)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if not updates:
            return

        updates.append("updated_at = ?")
        params.append(now)
        params.append(provider_id)

        sql = f"UPDATE provider_records SET {', '.join(updates)} WHERE provider_id = ?"

        with get_db_connection(db_path) as conn:
            conn.execute(sql, tuple(params))

    async def update(
        self,
        provider_id: str,
        display_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        enabled: bool | None = None,
        db_path: str | None = None,
    ) -> None:
        """Update fields of an existing provider record."""
        await asyncio.to_thread(
            self._update_sync, provider_id, display_name, api_key, base_url, enabled, db_path
        )

    @staticmethod
    def _delete_sync(provider_id: str, db_path: str | None) -> None:
        with get_db_connection(db_path) as conn:
            conn.execute("DELETE FROM provider_records WHERE provider_id = ?", (provider_id,))

    async def delete(self, provider_id: str, db_path: str | None = None) -> None:
        """Delete a provider record by provider_id."""
        await asyncio.to_thread(self._delete_sync, provider_id, db_path)

    def decrypt_key(self, api_key_encrypted: str) -> str:
        """Decrypt a provider API key using the current encryption key."""
        encryption_key = get_encryption_key()
        return decrypt_val(api_key_encrypted, encryption_key)


class ModelMappingRepository:
    """Repository for logical model name mappings to NVIDIA model names."""

    @staticmethod
    def _create_sync(logical_model: str, nvidia_model: str, db_path: str | None) -> ModelMapping:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO model_mappings (logical_model, nvidia_model, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(logical_model) DO UPDATE SET
                    nvidia_model = excluded.nvidia_model,
                    updated_at = excluded.updated_at
                """,
                (logical_model, nvidia_model, now, now),
            )
            row_id = cursor.lastrowid
            return ModelMapping(
                id=row_id,
                logical_model=logical_model,
                nvidia_model=nvidia_model,
                created_at=now,
                updated_at=now,
            )

    async def create(
        self, logical_model: str, nvidia_model: str, db_path: str | None = None
    ) -> ModelMapping:
        """Create or update a model mapping."""
        return await asyncio.to_thread(self._create_sync, logical_model, nvidia_model, db_path)

    @staticmethod
    def _get_nvidia_model_sync(logical_model: str, db_path: str | None) -> str | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT nvidia_model FROM model_mappings WHERE logical_model = ?",
                (logical_model,),
            )
            row = cursor.fetchone()
            return row["nvidia_model"] if row else None

    async def get_nvidia_model(self, logical_model: str, db_path: str | None = None) -> str | None:
        """Retrieve the target NVIDIA model for a given logical model name."""
        return await asyncio.to_thread(self._get_nvidia_model_sync, logical_model, db_path)

    @staticmethod
    def _get_all_sync(db_path: str | None) -> list[ModelMapping]:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, logical_model, nvidia_model, created_at, updated_at
                FROM model_mappings
                """
            )
            rows = cursor.fetchall()
            return [
                ModelMapping(
                    id=row["id"],
                    logical_model=row["logical_model"],
                    nvidia_model=row["nvidia_model"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    async def get_all(self, db_path: str | None = None) -> list[ModelMapping]:
        """Retrieve all model mappings."""
        return await asyncio.to_thread(self._get_all_sync, db_path)

    @staticmethod
    def _update_sync(logical_model: str, nvidia_model: str, db_path: str | None) -> None:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE model_mappings SET nvidia_model = ?, updated_at = ?
                WHERE logical_model = ?
                """,
                (nvidia_model, now, logical_model),
            )

    async def update(
        self, logical_model: str, nvidia_model: str, db_path: str | None = None
    ) -> None:
        """Update mapping destination for a logical model name."""
        await asyncio.to_thread(self._update_sync, logical_model, nvidia_model, db_path)

    @staticmethod
    def _delete_sync(logical_model: str, db_path: str | None) -> None:
        with get_db_connection(db_path) as conn:
            conn.execute("DELETE FROM model_mappings WHERE logical_model = ?", (logical_model,))

    async def delete(self, logical_model: str, db_path: str | None = None) -> None:
        """Delete a model mapping by logical model name."""
        await asyncio.to_thread(self._delete_sync, logical_model, db_path)


class LogRepository:
    """Repository for audit logs (requests, responses, errors, usage metrics)."""

    @staticmethod
    def _log_request_sync(request_id: str, model: str, stream: bool, db_path: str | None) -> None:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO request_logs (request_id, model, stream, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO NOTHING
                """,
                (request_id, model, 1 if stream else 0, now),
            )

    async def log_request(
        self, request_id: str, model: str, stream: bool, db_path: str | None = None
    ) -> None:
        """Record an incoming request log entry."""
        await asyncio.to_thread(self._log_request_sync, request_id, model, stream, db_path)

    @staticmethod
    def _update_request_status_sync(
        request_id: str,
        status_code: int,
        latency_ms: int,
        provider_id: str | None,
        db_path: str | None,
    ) -> None:
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                UPDATE request_logs
                SET status_code = ?, latency_ms = ?, provider_id = COALESCE(?, provider_id)
                WHERE request_id = ?
                """,
                (status_code, latency_ms, provider_id, request_id),
            )

    async def update_request_status(
        self,
        request_id: str,
        status_code: int,
        latency_ms: int,
        provider_id: str | None = None,
        db_path: str | None = None,
    ) -> None:
        """Update HTTP status code, latency, and provider ID of a request."""
        await asyncio.to_thread(
            self._update_request_status_sync,
            request_id,
            status_code,
            latency_ms,
            provider_id,
            db_path,
        )

    @staticmethod
    def _log_response_sync(
        request_id: str, content: str, stop_reason: str | None, db_path: str | None
    ) -> None:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO response_logs (request_id, content, stop_reason, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    content = excluded.content,
                    stop_reason = excluded.stop_reason
                """,
                (request_id, content, stop_reason, now),
            )

    async def log_response(
        self,
        request_id: str,
        content: str,
        stop_reason: str | None = None,
        db_path: str | None = None,
    ) -> None:
        """Log cumulative response details for a request."""
        await asyncio.to_thread(self._log_response_sync, request_id, content, stop_reason, db_path)

    @staticmethod
    def _log_error_sync(
        request_id: str | None, error_type: str, error_message: str, db_path: str | None
    ) -> None:
        now = datetime.now().isoformat()
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO error_logs (request_id, error_type, error_message, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    error_type = excluded.error_type,
                    error_message = excluded.error_message
                """,
                (request_id, error_type, error_message, now),
            )

    async def log_error(
        self,
        request_id: str | None,
        error_type: str,
        error_message: str,
        db_path: str | None = None,
    ) -> None:
        """Log failure characteristics of an execution error."""
        await asyncio.to_thread(
            self._log_error_sync, request_id, error_type, error_message, db_path
        )

    @staticmethod
    def _log_usage_sync(
        request_id: str, input_tokens: int, output_tokens: int, db_path: str | None
    ) -> None:
        now = datetime.now().isoformat()
        total_tokens = input_tokens + output_tokens
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_entries (
                    request_id, input_tokens, output_tokens, total_tokens, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens,
                    total_tokens = excluded.total_tokens
                """,
                (request_id, input_tokens, output_tokens, total_tokens, now),
            )

    async def log_usage(
        self, request_id: str, input_tokens: int, output_tokens: int, db_path: str | None = None
    ) -> None:
        """Log estimated token counts for input and output."""
        await asyncio.to_thread(
            self._log_usage_sync, request_id, input_tokens, output_tokens, db_path
        )

    @staticmethod
    def _get_request_logs_sync(limit: int, db_path: str | None) -> list[RequestLog]:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, request_id, model, stream, provider_id,
                       status_code, latency_ms, created_at
                FROM request_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                RequestLog(
                    id=row["id"],
                    request_id=row["request_id"],
                    model=row["model"],
                    stream=bool(row["stream"]),
                    provider_id=row["provider_id"],
                    status_code=row["status_code"],
                    latency_ms=row["latency_ms"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def get_request_logs(
        self, limit: int = 100, db_path: str | None = None
    ) -> list[RequestLog]:
        """Fetch request logs up to the limit."""
        return await asyncio.to_thread(self._get_request_logs_sync, limit, db_path)

    @staticmethod
    def _get_request_log_sync(request_id: str, db_path: str | None) -> RequestLog | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, request_id, model, stream, provider_id,
                       status_code, latency_ms, created_at
                FROM request_logs WHERE request_id = ?
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return RequestLog(
                id=row["id"],
                request_id=row["request_id"],
                model=row["model"],
                stream=bool(row["stream"]),
                provider_id=row["provider_id"],
                status_code=row["status_code"],
                latency_ms=row["latency_ms"],
                created_at=row["created_at"],
            )

    async def get_request_log(
        self, request_id: str, db_path: str | None = None
    ) -> RequestLog | None:
        """Fetch request log by request_id."""
        return await asyncio.to_thread(self._get_request_log_sync, request_id, db_path)

    @staticmethod
    def _get_response_log_sync(request_id: str, db_path: str | None) -> ResponseLog | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, request_id, content, stop_reason, created_at
                FROM response_logs WHERE request_id = ?
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ResponseLog(
                id=row["id"],
                request_id=row["request_id"],
                content=row["content"],
                stop_reason=row["stop_reason"],
                created_at=row["created_at"],
            )

    async def get_response_log(
        self, request_id: str, db_path: str | None = None
    ) -> ResponseLog | None:
        """Fetch response details for a request."""
        return await asyncio.to_thread(self._get_response_log_sync, request_id, db_path)

    @staticmethod
    def _get_error_log_sync(request_id: str, db_path: str | None) -> ErrorLog | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, request_id, error_type, error_message, created_at
                FROM error_logs WHERE request_id = ?
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return ErrorLog(
                id=row["id"],
                request_id=row["request_id"],
                error_type=row["error_type"],
                error_message=row["error_message"],
                created_at=row["created_at"],
            )

    async def get_error_log(self, request_id: str, db_path: str | None = None) -> ErrorLog | None:
        """Fetch error details for a request."""
        return await asyncio.to_thread(self._get_error_log_sync, request_id, db_path)

    @staticmethod
    def _get_usage_entry_sync(request_id: str, db_path: str | None) -> UsageEntry | None:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, request_id, input_tokens, output_tokens, total_tokens, created_at
                FROM usage_entries
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return UsageEntry(
                id=row["id"],
                request_id=row["request_id"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                created_at=row["created_at"],
            )

    async def get_usage_entry(
        self, request_id: str, db_path: str | None = None
    ) -> UsageEntry | None:
        """Fetch token usage statistics for a request."""
        return await asyncio.to_thread(self._get_usage_entry_sync, request_id, db_path)

    @staticmethod
    def _get_paginated_requests_sync(
        limit: int,
        offset: int,
        provider_id: str | None,
        status: str | None,
        start_date: str | None,
        end_date: str | None,
        db_path: str | None,
    ) -> list[RequestLog]:
        query = """
            SELECT id, request_id, model, stream, provider_id, status_code, latency_ms, created_at
            FROM request_logs
            WHERE 1=1
        """
        params = []
        if provider_id is not None:
            query += " AND provider_id = ?"
            params.append(provider_id)
        if status is not None:
            if status == "success":
                query += " AND status_code >= 200 AND status_code < 300"
            elif status == "error":
                query += " AND (status_code >= 400 OR status_code IS NULL)"
            else:
                try:
                    code = int(status)
                    query += " AND status_code = ?"
                    params.append(code)
                except ValueError:
                    pass
        if start_date is not None:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND created_at <= ?"
            params.append(end_date)

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                RequestLog(
                    id=row["id"],
                    request_id=row["request_id"],
                    model=row["model"],
                    stream=bool(row["stream"]),
                    provider_id=row["provider_id"],
                    status_code=row["status_code"],
                    latency_ms=row["latency_ms"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    async def get_paginated_requests(
        self,
        limit: int = 20,
        offset: int = 0,
        provider_id: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        db_path: str | None = None,
    ) -> list[RequestLog]:
        """Fetch paginated request logs with filters."""
        return await asyncio.to_thread(
            self._get_paginated_requests_sync,
            limit,
            offset,
            provider_id,
            status,
            start_date,
            end_date,
            db_path,
        )

    @staticmethod
    def _get_paginated_errors_sync(
        limit: int,
        offset: int,
        error_type: str | None,
        provider_id: str | None,
        start_date: str | None,
        end_date: str | None,
        db_path: str | None,
    ) -> list[dict]:
        query = """
            SELECT e.id, e.request_id, e.error_type, e.error_message, e.created_at,
                   r.provider_id, r.model
            FROM error_logs e
            LEFT JOIN request_logs r ON e.request_id = r.request_id
            WHERE 1=1
        """
        params = []
        if error_type is not None:
            query += " AND e.error_type = ?"
            params.append(error_type)
        if provider_id is not None:
            query += " AND r.provider_id = ?"
            params.append(provider_id)
        if start_date is not None:
            query += " AND e.created_at >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND e.created_at <= ?"
            params.append(end_date)

        query += " ORDER BY e.id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "request_id": row["request_id"],
                    "error_type": row["error_type"],
                    "error_message": row["error_message"],
                    "created_at": row["created_at"],
                    "provider_id": row["provider_id"],
                    "model": row["model"],
                }
                for row in rows
            ]

    async def get_paginated_errors(
        self,
        limit: int = 20,
        offset: int = 0,
        error_type: str | None = None,
        provider_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        db_path: str | None = None,
    ) -> list[dict]:
        """Fetch paginated error logs with filters."""
        return await asyncio.to_thread(
            self._get_paginated_errors_sync,
            limit,
            offset,
            error_type,
            provider_id,
            start_date,
            end_date,
            db_path,
        )

    @staticmethod
    def _get_usage_summary_sync(db_path: str | None) -> dict:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # 1. Total summary
            cursor.execute(
                """
                SELECT COUNT(r.id) as total_requests,
                       COALESCE(SUM(u.input_tokens), 0) as total_input_tokens,
                       COALESCE(SUM(u.output_tokens), 0) as total_output_tokens,
                       COALESCE(SUM(u.total_tokens), 0) as total_tokens
                FROM request_logs r
                LEFT JOIN usage_entries u ON r.request_id = u.request_id
                """
            )
            summary_row = cursor.fetchone()
            summary = {
                "total_requests": summary_row["total_requests"],
                "total_input_tokens": summary_row["total_input_tokens"],
                "total_output_tokens": summary_row["total_output_tokens"],
                "total_tokens": summary_row["total_tokens"],
            }

            # 2. Daily usage
            cursor.execute(
                """
                SELECT strftime('%Y-%m-%d', r.created_at) as day,
                       COUNT(r.id) as request_count,
                       COALESCE(SUM(u.input_tokens), 0) as input_tokens,
                       COALESCE(SUM(u.output_tokens), 0) as output_tokens,
                       COALESCE(SUM(u.total_tokens), 0) as total_tokens
                FROM request_logs r
                LEFT JOIN usage_entries u ON r.request_id = u.request_id
                GROUP BY day
                ORDER BY day DESC
                LIMIT 30
                """
            )
            summary["daily_usage"] = [
                {
                    "day": r["day"],
                    "request_count": r["request_count"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "total_tokens": r["total_tokens"],
                }
                for r in cursor.fetchall()
            ]

            # 3. Provider usage
            cursor.execute(
                """
                SELECT COALESCE(r.provider_id, 'unknown') as provider_id,
                       COUNT(r.id) as request_count,
                       COALESCE(SUM(u.input_tokens), 0) as input_tokens,
                       COALESCE(SUM(u.output_tokens), 0) as output_tokens,
                       COALESCE(SUM(u.total_tokens), 0) as total_tokens
                FROM request_logs r
                LEFT JOIN usage_entries u ON r.request_id = u.request_id
                GROUP BY provider_id
                ORDER BY total_tokens DESC
                """
            )
            summary["provider_usage"] = [
                {
                    "provider_id": r["provider_id"],
                    "request_count": r["request_count"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "total_tokens": r["total_tokens"],
                }
                for r in cursor.fetchall()
            ]

            # 4. Model usage
            cursor.execute(
                """
                SELECT r.model,
                       COUNT(r.id) as request_count,
                       COALESCE(SUM(u.input_tokens), 0) as input_tokens,
                       COALESCE(SUM(u.output_tokens), 0) as output_tokens,
                       COALESCE(SUM(u.total_tokens), 0) as total_tokens
                FROM request_logs r
                LEFT JOIN usage_entries u ON r.request_id = u.request_id
                GROUP BY r.model
                ORDER BY total_tokens DESC
                """
            )
            summary["model_usage"] = [
                {
                    "model": r["model"],
                    "request_count": r["request_count"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "total_tokens": r["total_tokens"],
                }
                for r in cursor.fetchall()
            ]

            return summary

    async def get_usage_summary(self, db_path: str | None = None) -> dict:
        """Fetch request and token usage stats aggregated by day, provider, and model."""
        return await asyncio.to_thread(self._get_usage_summary_sync, db_path)

    @staticmethod
    def _get_total_requests_and_errors_sync(db_path: str | None) -> tuple[int, int]:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) as total FROM request_logs")
            total = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT COUNT(id) as errors FROM request_logs
                WHERE status_code >= 400 OR status_code IS NULL
                """
            )
            errors = cursor.fetchone()["errors"]
            return total, errors

    async def get_total_requests_and_errors(self, db_path: str | None = None) -> tuple[int, int]:
        """Fetch total requests and error requests count for success rate."""
        return await asyncio.to_thread(self._get_total_requests_and_errors_sync, db_path)

    @staticmethod
    def _clear_all_logs_sync(db_path: str | None) -> None:
        with get_db_connection(db_path) as conn:
            conn.execute("DELETE FROM response_logs;")
            conn.execute("DELETE FROM error_logs;")
            conn.execute("DELETE FROM usage_entries;")
            conn.execute("DELETE FROM request_logs;")

    async def clear_all_logs(self, db_path: str | None = None) -> None:
        """Truncate all logging tables in the database."""
        await asyncio.to_thread(self._clear_all_logs_sync, db_path)
