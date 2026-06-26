# AEGIS Database Schema

## 1. Purpose

This document defines the SQLite schema for AEGIS V1.

The schema should store configuration, provider pool metadata, runtime settings, and logs in a lightweight and maintainable way.

---

## 2. Design Principles

- keep the schema minimal
- prefer explicit columns over JSON blobs when practical
- separate static config from runtime state
- store secrets carefully
- make queries simple and predictable
- design for future migration support

---

## 3. Tables

## 3.1 `settings`
Stores global AEGIS settings.

### Columns
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

### Examples
- `auth_token`
- `default_model`
- `scheduler_mode`
- `streaming_enabled`

---

## 3.2 `provider_members`
Stores NVIDIA pool members.

### Columns
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name` TEXT NOT NULL
- `label` TEXT
- `api_key_encrypted` TEXT NOT NULL
- `enabled` INTEGER NOT NULL DEFAULT 1
- `healthy` INTEGER NOT NULL DEFAULT 1
- `active_requests` INTEGER NOT NULL DEFAULT 0
- `cooldown_until` TEXT
- `last_used_at` TEXT
- `last_success_at` TEXT
- `last_error_at` TEXT
- `recent_error_count` INTEGER NOT NULL DEFAULT 0
- `rpm_window_usage` INTEGER NOT NULL DEFAULT 0
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

### Notes
- `api_key_encrypted` should never be stored in plaintext if encryption support is available.
- `label` may be used to show an email or friendly account name in the UI.

---

## 3.3 `runtime_state`
Stores current runtime decisions or cached operational metadata.

### Columns
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL
- `updated_at` TEXT NOT NULL

### Examples
- last scheduler choice
- last health snapshot
- last restart reason

---

## 3.4 `request_logs`
Stores request and error metadata for debugging.

### Columns
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `request_id` TEXT NOT NULL
- `route` TEXT NOT NULL
- `provider_member_id` INTEGER
- `status` TEXT NOT NULL
- `latency_ms` INTEGER
- `error_type` TEXT
- `error_message` TEXT
- `created_at` TEXT NOT NULL

### Indexes
- index on `request_id`
- index on `created_at`
- index on `provider_member_id`

---

## 4. Optional Supporting Table

## 4.1 `events`
If the project wants a more structured operational log later, an `events` table can be added.

### Columns
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `event_type` TEXT NOT NULL
- `payload_json` TEXT NOT NULL
- `created_at` TEXT NOT NULL

This table is optional for V1.

---

## 5. Migration Rules

- keep migrations explicit
- avoid destructive changes without versioning
- add columns rather than rewriting tables when possible
- preserve backward compatibility for config tables

---

## 6. Suggested SQLite Usage

Use SQLite for:
- settings persistence
- provider member records
- health snapshots
- request logs
- startup metadata

Do not use SQLite for high-volume token storage or large raw response archives in V1.

---

## 7. Security Notes

- never store raw API keys in plaintext if avoidable
- never expose stored secrets through logs
- separate secret storage from public UI data
- only show non-sensitive metadata in Control Center views

---

## 8. Final Schema Goal

The schema should be easy to query, simple to migrate, and small enough that AEGIS remains lightweight in V1.
