"""AEGIS database utilities — Connection context and secret encryption.

Follows ARCHITECTURE.md §10 and security rules.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from aegis.config.settings import get_settings


@contextmanager
def get_db_connection(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Provide a thread-safe connection context for SQLite database queries.

    Enforces foreign key checks and row-to-dictionary factory configuration.
    """
    if db_path is None:
        db_path = get_settings().database_path

    # Ensure parent directories exist
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_encryption_key() -> str:
    """Resolve the encryption key from Settings, falling back to a hashed static key."""
    settings = get_settings()
    if settings.encryption_key:
        return settings.encryption_key
    if settings.auth_token:
        return settings.auth_token
    return "aegis-default-secret-key-12345"


def encrypt_val(val: str, secret_key: str) -> str:
    """Encrypt a string value using a sha256 stream-cipher XOR cipher."""
    if not val:
        return ""
    key_bytes = hashlib.sha256(secret_key.encode("utf-8")).digest()
    val_bytes = val.encode("utf-8")
    encrypted = bytearray()
    for i, b in enumerate(val_bytes):
        key_byte = key_bytes[i % len(key_bytes)]
        encrypted.append(b ^ key_byte)
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_val(encrypted_str: str, secret_key: str) -> str:
    """Decrypt a string value using a sha256 stream-cipher XOR cipher."""
    if not encrypted_str:
        return ""
    key_bytes = hashlib.sha256(secret_key.encode("utf-8")).digest()
    encrypted_bytes = base64.b64decode(encrypted_str.encode("utf-8"))
    decrypted = bytearray()
    for i, b in enumerate(encrypted_bytes):
        key_byte = key_bytes[i % len(key_bytes)]
        decrypted.append(b ^ key_byte)
    return decrypted.decode("utf-8")
