"""Tests for RouteFlow configuration and settings.

Verifies:
- Default values load correctly
- Environment variables override defaults
- Settings caching works
"""

import pathlib

import pytest

from routeflow.config.settings import AegisSettings, get_settings


class TestAegisSettingsDefaults:
    """Verify that default values match ENVIRONMENT_REFERENCE.md §5."""

    def test_default_host(self) -> None:
        settings = AegisSettings()
        assert settings.host == "0.0.0.0"

    def test_default_port(self) -> None:
        settings = AegisSettings()
        assert settings.port == 8000

    def test_default_log_level(self) -> None:
        settings = AegisSettings()
        assert settings.log_level == "INFO"

    def test_default_scheduler_mode(self) -> None:
        settings = AegisSettings()
        assert settings.scheduler_mode == "health-first"

    def test_default_retry_count(self) -> None:
        settings = AegisSettings()
        assert settings.retry_count == 2

    def test_default_timeout_seconds(self) -> None:
        settings = AegisSettings()
        assert settings.timeout_seconds == 60

    def test_default_streaming_enabled(self) -> None:
        settings = AegisSettings()
        assert settings.streaming_enabled is True

    def test_default_thinking_enabled(self) -> None:
        settings = AegisSettings()
        assert settings.thinking_enabled is True

    def test_default_max_request_size_mb(self) -> None:
        settings = AegisSettings()
        assert settings.max_request_size_mb == 10

    def test_default_auth_token_is_none(self) -> None:
        settings = AegisSettings()
        assert settings.auth_token is None

    def test_default_encryption_key_is_none(self) -> None:
        settings = AegisSettings()
        assert settings.encryption_key is None

    def test_default_database_path(self) -> None:
        settings = AegisSettings()
        assert settings.database_path == "routeflow.db"


class TestAegisSettingsOverride:
    """Verify that environment variables override defaults."""

    def test_port_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROUTEFLOW_PORT", "9000")
        settings = AegisSettings()
        assert settings.port == 9000

    def test_log_level_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROUTEFLOW_LOG_LEVEL", "DEBUG")
        settings = AegisSettings()
        assert settings.log_level == "DEBUG"

    def test_streaming_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROUTEFLOW_STREAMING_ENABLED", "false")
        settings = AegisSettings()
        assert settings.streaming_enabled is False

    def test_auth_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROUTEFLOW_AUTH_TOKEN", "test-secret-token")
        settings = AegisSettings()
        assert settings.auth_token == "test-secret-token"

    def test_scheduler_mode_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROUTEFLOW_SCHEDULER_MODE", "round-robin")
        settings = AegisSettings()
        assert settings.scheduler_mode == "round-robin"


class TestGetSettingsCache:
    """Verify the cached settings function."""

    def test_get_settings_returns_instance(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, AegisSettings)

    def test_get_settings_is_cached(self) -> None:
        get_settings.cache_clear()
        first = get_settings()
        second = get_settings()
        assert first is second


def test_settings_database_override_whitelisting(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that settings overrides from database respect whitelisting."""
    import sqlite3

    db_file = tmp_path / "test_overrides.db"

    # 1. Setup database with whitelisted and non-whitelisted configurations
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO settings VALUES ('default_model', 'db-model', '2026-01-01')")
    conn.execute("INSERT INTO settings VALUES ('auth_token', 'db-bypass-token', '2026-01-01')")
    conn.commit()
    conn.close()

    # Configure database path via monkeypatch
    monkeypatch.setenv("ROUTEFLOW_DATABASE_PATH", str(db_file))
    get_settings.cache_clear()

    # Load settings
    settings = get_settings()

    # Whitelisted should be updated
    assert settings.default_model == "db-model"
    # Non-whitelisted should remain default (None)
    assert settings.auth_token is None
    get_settings.cache_clear()


def test_settings_database_parse_error_warning(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that setting values failing to parse log a warning."""
    import sqlite3
    from unittest.mock import patch

    db_file = tmp_path / "test_warnings.db"

    # Insert malformed integer value
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    conn.execute("INSERT INTO settings VALUES ('retry_count', 'not-an-integer', '2026-01-01')")
    conn.commit()
    conn.close()

    monkeypatch.setenv("ROUTEFLOW_DATABASE_PATH", str(db_file))
    get_settings.cache_clear()

    with patch("logging.Logger.warning") as mock_warning:
        get_settings()
        # A warning should be logged for the parse error
        mock_warning.assert_called()
        log_message = mock_warning.call_args[0][0]
        assert "Failed to load settings overrides" in log_message
    get_settings.cache_clear()
