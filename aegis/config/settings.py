"""AEGIS settings — Environment-driven configuration using Pydantic Settings.

All settings are loaded from environment variables prefixed with AEGIS_.
See ENVIRONMENT_REFERENCE.md for the full list of supported variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AegisSettings(BaseSettings):
    """Core AEGIS configuration loaded from environment variables.

    Each field maps to an AEGIS_<FIELD_NAME> environment variable.
    For example, ``auth_token`` maps to ``AEGIS_AUTH_TOKEN``.
    """

    model_config = SettingsConfigDict(
        env_prefix="AEGIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    auth_token: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    database_path: str = "aegis.db"
    encryption_key: str | None = None

    # --- Model ---
    default_model: str = "claude-sonnet-4-20250514"

    # --- Runtime ---
    scheduler_mode: str = "health-first"
    retry_count: int = 2
    timeout_seconds: int = 60
    streaming_enabled: bool = True
    thinking_enabled: bool = True
    max_request_size_mb: int = 10


@lru_cache(maxsize=1)
def get_settings() -> AegisSettings:
    """Return the cached application settings instance.

    Settings are loaded once and cached for the lifetime of the process.
    Call ``get_settings.cache_clear()`` if you need to reload (e.g. in tests).
    """
    return AegisSettings()
