"""AEGIS settings — Environment-driven configuration using Pydantic Settings.

All settings are loaded from environment variables prefixed with AEGIS_.
See ENVIRONMENT_REFERENCE.md for the full list of supported variables.
"""

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


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


# Safe whitelist of configuration keys allowed to be overridden dynamically from the database
SETTINGS_WHITELIST = {
    "default_model",
    "scheduler_mode",
    "retry_count",
    "timeout_seconds",
    "streaming_enabled",
    "thinking_enabled",
    "max_request_size_mb",
    "log_level",
}


@lru_cache(maxsize=1)
def get_settings() -> AegisSettings:
    """Return the cached application settings instance.

    Settings are loaded once and cached for the lifetime of the process.
    If database tables exist, overrides them dynamically.
    Call ``get_settings.cache_clear()`` if you need to reload (e.g. in tests).
    """
    settings = AegisSettings()
    try:
        import sqlite3

        conn = sqlite3.connect(settings.database_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        for row in rows:
            key = row["key"]
            val = row["value"]
            if key in SETTINGS_WHITELIST and hasattr(settings, key):
                current_val = getattr(settings, key)
                field_type = type(current_val) if current_val is not None else str
                if field_type is bool:
                    setattr(settings, key, val.lower() in ("true", "1", "yes"))
                else:
                    setattr(settings, key, field_type(val))
        conn.close()
    except sqlite3.OperationalError:
        # Table might not exist yet during initial startup/migrations. This is expected.
        pass
    except Exception as exc:
        from aegis.core.logging import get_logger

        get_logger(__name__).warning(
            "Failed to load settings overrides from database: %s", str(exc)
        )
    return settings
