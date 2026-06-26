"""Unit tests for the AEGIS SQLite persistence layer.

Verifies:
- Migration run-through and schema versioning
- SettingsRepository CRUD
- ProviderRecordRepository CRUD (including API key encryption/decryption)
- ModelMappingRepository CRUD
- LogRepository logging and retrieval
"""

from __future__ import annotations

import pathlib

import pytest

from aegis.persistence.db import decrypt_val, encrypt_val, get_db_connection
from aegis.persistence.migrations import run_migrations
from aegis.persistence.repositories import (
    LogRepository,
    ModelMappingRepository,
    ProviderRecordRepository,
    SettingsRepository,
)


@pytest.fixture
def db_path(tmp_path: pathlib.Path) -> str:
    """Fixture returning a unique file path for a test database."""
    return str(tmp_path / "test_aegis.db")


# ===========================================================================
# Migration and Connection Tests
# ===========================================================================


def test_migrations_and_version_tracking(db_path: str) -> None:
    """Verify that migrations initialize the schema version and create tables."""
    # 1. Run migrations
    run_migrations(db_path)

    # 2. Check the schema version
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) as max_ver FROM schema_version")
        row = cursor.fetchone()
        assert row["max_ver"] == 1

        # 3. Check that tables exist
        cursor.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table'
              AND name IN (
                  'settings', 'provider_records', 'model_mappings', 'request_logs'
              )
            """
        )
        tables = [r["name"] for r in cursor.fetchall()]
        assert "settings" in tables
        assert "provider_records" in tables
        assert "model_mappings" in tables
        assert "request_logs" in tables


def test_migration_is_idempotent(db_path: str) -> None:
    """Verify that running migrations multiple times does not crash or double-apply."""
    run_migrations(db_path)
    run_migrations(db_path)  # Should not raise exception or break table state


# ===========================================================================
# Encryption Helper Tests
# ===========================================================================


def test_encryption_decryption_helpers() -> None:
    """Verify stream cipher XOR encryption utility matches original text after decrypting."""
    secret = "my-encryption-key-123"
    plain_text = "sk-nvidia-nim-abcdef12345"

    enc = encrypt_val(plain_text, secret)
    assert enc != plain_text
    assert len(enc) > 0

    dec = decrypt_val(enc, secret)
    assert dec == plain_text


# ===========================================================================
# Settings Repository Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_settings_repository(db_path: str) -> None:
    """Verify CRUD and dictionary retrieval in SettingsRepository."""
    run_migrations(db_path)
    repo = SettingsRepository()

    # 1. Retrieve non-existent setting
    non_existent = await repo.get("mode", db_path)
    assert non_existent is None

    # 2. Set settings
    await repo.set("default_model", "claude-sonnet-4", db_path)
    await repo.set("retry_count", "3", db_path)

    # 3. Get single setting
    setting = await repo.get("default_model", db_path)
    assert setting is not None
    assert setting.key == "default_model"
    assert setting.value == "claude-sonnet-4"

    # 4. Get all settings as dict
    all_settings = await repo.get_all(db_path)
    assert len(all_settings) == 2
    assert all_settings["default_model"] == "claude-sonnet-4"
    assert all_settings["retry_count"] == "3"

    # 5. Overwrite setting
    await repo.set("default_model", "claude-opus-3", db_path)
    updated = await repo.get("default_model", db_path)
    assert updated.value == "claude-opus-3"


# ===========================================================================
# Provider Records Repository Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_provider_record_repository(db_path: str) -> None:
    """Verify CRUD and encryption safety in ProviderRecordRepository."""
    run_migrations(db_path)
    repo = ProviderRecordRepository()

    # 1. Create a provider record
    record = await repo.create(
        provider_id="nvidia-acc-1",
        display_name="First NVIDIA NIM Account",
        api_key="nvapi-key-test-12345",
        base_url="https://api.nvidia.com/v1",
        enabled=True,
        db_path=db_path,
    )
    assert record.provider_id == "nvidia-acc-1"
    assert record.display_name == "First NVIDIA NIM Account"
    # Ensure api key is stored encrypted in Pydantic record
    assert record.api_key_encrypted != "nvapi-key-test-12345"

    # Verify key is stored encrypted in raw DB row
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT api_key_encrypted FROM provider_records WHERE provider_id = 'nvidia-acc-1'"
        )
        row = cursor.fetchone()
        assert row["api_key_encrypted"] == record.api_key_encrypted
        assert row["api_key_encrypted"] != "nvapi-key-test-12345"

    # 2. Decrypt api key using repository decryption helper
    decrypted = repo.decrypt_key(record.api_key_encrypted)
    assert decrypted == "nvapi-key-test-12345"

    # 3. Retrieve provider record
    fetched = await repo.get("nvidia-acc-1", db_path)
    assert fetched is not None
    assert fetched.display_name == "First NVIDIA NIM Account"
    assert repo.decrypt_key(fetched.api_key_encrypted) == "nvapi-key-test-12345"

    # 4. Update provider record
    await repo.update(
        provider_id="nvidia-acc-1",
        display_name="Updated Label",
        api_key="new-key-6789",
        enabled=False,
        db_path=db_path,
    )
    updated = await repo.get("nvidia-acc-1", db_path)
    assert updated.display_name == "Updated Label"
    assert updated.enabled is False
    assert repo.decrypt_key(updated.api_key_encrypted) == "new-key-6789"

    # 5. List all provider records
    all_providers = await repo.get_all(db_path)
    assert len(all_providers) == 1
    assert all_providers[0].provider_id == "nvidia-acc-1"

    # 6. Delete provider record
    await repo.delete("nvidia-acc-1", db_path)
    deleted = await repo.get("nvidia-acc-1", db_path)
    assert deleted is None


# ===========================================================================
# Model Mappings Repository Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_model_mapping_repository(db_path: str) -> None:
    """Verify CRUD operations for logical-to-NVIDIA model name mapping."""
    run_migrations(db_path)
    repo = ModelMappingRepository()

    # 1. Create mapping
    mapping = await repo.create("claude-sonnet", "meta/llama3-70b", db_path)
    assert mapping.logical_model == "claude-sonnet"
    assert mapping.nvidia_model == "meta/llama3-70b"

    # 2. Retrieve mapping destination
    dest = await repo.get_nvidia_model("claude-sonnet", db_path)
    assert dest == "meta/llama3-70b"

    # 3. Update mapping
    await repo.create("claude-sonnet", "meta/llama3-8b", db_path)  # Overwrite via create
    dest_updated = await repo.get_nvidia_model("claude-sonnet", db_path)
    assert dest_updated == "meta/llama3-8b"

    # 4. List all mappings
    all_mappings = await repo.get_all(db_path)
    assert len(all_mappings) == 1
    assert all_mappings[0].logical_model == "claude-sonnet"

    # 5. Delete mapping
    await repo.delete("claude-sonnet", db_path)
    dest_deleted = await repo.get_nvidia_model("claude-sonnet", db_path)
    assert dest_deleted is None


# ===========================================================================
# Logging Repository Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_logging_repository(db_path: str) -> None:
    """Verify insertion, status updates, and child record logging in LogRepository."""
    run_migrations(db_path)
    repo = LogRepository()

    req_id = "req-12345"

    # 1. Log request entry
    await repo.log_request(req_id, "claude-sonnet-4", stream=False, db_path=db_path)

    # Verify log request exists
    logs = await repo.get_request_logs(10, db_path)
    assert len(logs) == 1
    assert logs[0].request_id == req_id
    assert logs[0].model == "claude-sonnet-4"
    assert logs[0].stream is False

    # 2. Log response
    await repo.log_response(req_id, content="Hi client!", stop_reason="end_turn", db_path=db_path)
    resp = await repo.get_response_log(req_id, db_path)
    assert resp is not None
    assert resp.content == "Hi client!"
    assert resp.stop_reason == "end_turn"

    # 3. Log error
    await repo.log_error(
        req_id, error_type="rate_limited", error_message="Too fast", db_path=db_path
    )
    err = await repo.get_error_log(req_id, db_path)
    assert err is not None
    assert err.error_type == "rate_limited"
    assert err.error_message == "Too fast"

    # 4. Log usage metrics
    await repo.log_usage(req_id, input_tokens=15, output_tokens=30, db_path=db_path)
    usage = await repo.get_usage_entry(req_id, db_path)
    assert usage is not None
    assert usage.input_tokens == 15
    assert usage.output_tokens == 30
    assert usage.total_tokens == 45

    # 5. Update status code and latency
    await repo.update_request_status(req_id, status_code=200, latency_ms=125, db_path=db_path)
    logs_updated = await repo.get_request_logs(10, db_path)
    assert logs_updated[0].status_code == 200
    assert logs_updated[0].latency_ms == 125
