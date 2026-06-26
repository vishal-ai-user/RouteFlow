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

    Enforces foreign key checks, WAL mode, synchronous normal, and row dictionary factory.
    """
    if db_path is None:
        db_path = get_settings().database_path

    # Ensure parent directories exist
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
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


def derive_fernet_key(secret_key: str) -> bytes:
    """Derive a 32-byte urlsafe base64 key from an arbitrary secret key string."""
    key_hash = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(key_hash)


def encrypt_val(val: str, secret_key: str) -> str:
    """Encrypt a string value using standard authenticated Fernet encryption."""
    if not val:
        return ""
    from cryptography.fernet import Fernet

    fernet_key = derive_fernet_key(secret_key)
    f = Fernet(fernet_key)
    return f.encrypt(val.encode("utf-8")).decode("utf-8")


def decrypt_val(encrypted_str: str, secret_key: str) -> str:
    """Decrypt a string value using Fernet, falling back to legacy XOR if needed."""
    if not encrypted_str:
        return ""
    from cryptography.fernet import Fernet, InvalidToken

    try:
        fernet_key = derive_fernet_key(secret_key)
        f = Fernet(fernet_key)
        return f.decrypt(encrypted_str.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        # Legacy fallback: XOR decryption
        try:
            key_bytes = hashlib.sha256(secret_key.encode("utf-8")).digest()
            encrypted_bytes = base64.b64decode(encrypted_str.encode("utf-8"))
            decrypted = bytearray()
            for i, b in enumerate(encrypted_bytes):
                key_byte = key_bytes[i % len(key_bytes)]
                decrypted.append(b ^ key_byte)
            return decrypted.decode("utf-8")
        except Exception:
            return ""
