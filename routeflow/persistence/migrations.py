"""RouteFlow persistence migrations — SQLite schema initialization and upgrades.

Follows ARCHITECTURE.md §10 and migration rules.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from routeflow.core.logging import get_logger
from routeflow.persistence.db import get_db_connection

logger = get_logger(__name__)

# List of migrations where index + 1 represents the schema version.
MIGRATIONS = [
    # Version 1: Initial schema setup
    """
    -- Settings table
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Provider records table
    CREATE TABLE IF NOT EXISTS provider_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_id TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL,
        api_key_encrypted TEXT NOT NULL,
        base_url TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Model mappings table
    CREATE TABLE IF NOT EXISTS model_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        logical_model TEXT NOT NULL UNIQUE,
        nvidia_model TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    -- Request logs table
    CREATE TABLE IF NOT EXISTS request_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL UNIQUE,
        model TEXT NOT NULL,
        stream INTEGER NOT NULL,
        provider_id TEXT,
        status_code INTEGER,
        latency_ms INTEGER,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_request_logs_request_id ON request_logs(request_id);
    CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at);

    -- Response logs table
    CREATE TABLE IF NOT EXISTS response_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL UNIQUE,
        content TEXT,
        stop_reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES request_logs(request_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_response_logs_request_id ON response_logs(request_id);

    -- Error logs table
    CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT UNIQUE,
        error_type TEXT NOT NULL,
        error_message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES request_logs(request_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_error_logs_request_id ON error_logs(request_id);

    -- Usage entries table
    CREATE TABLE IF NOT EXISTS usage_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id TEXT NOT NULL UNIQUE,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (request_id) REFERENCES request_logs(request_id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_usage_entries_request_id ON usage_entries(request_id);
    """
]


def run_migrations(db_path: str | None = None) -> None:
    """Initialize a fresh database or apply pending schema migrations."""
    logger.info("Running database migrations...")
    with get_db_connection(db_path) as conn:
        # 1. Create schema_version tracking table if it does not exist.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """
        )

        # 2. Retrieve the currently applied version.
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) as current_version FROM schema_version")
        row = cursor.fetchone()
        current_version = (
            row["current_version"] if row and row["current_version"] is not None else 0
        )

        logger.info("Current database schema version: %d", current_version)

        # 3. Apply pending migrations sequentially.
        for i, migration_sql in enumerate(MIGRATIONS):
            version = i + 1
            if version > current_version:
                logger.info("Applying migration to version %d", version)
                try:
                    # Execute script can contain multiple statements
                    conn.executescript(migration_sql)
                    conn.execute(
                        "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                        (version, datetime.now().isoformat()),
                    )
                    logger.info("Successfully applied migration to version %d", version)
                except sqlite3.Error as err:
                    logger.error("Failed to apply migration to version %d: %s", version, str(err))
                    raise

    logger.info("Database migrations complete.")
