# AEGIS Environment Reference

## 1. Purpose

This document defines the environment variables and runtime configuration expected by AEGIS.

---

## 2. Core Environment Variables

### `AEGIS_AUTH_TOKEN`
Primary gateway authentication token.

### `AEGIS_ENCRYPTION_KEY`
Key used to encrypt sensitive stored values if encryption is enabled.

### `AEGIS_DATABASE_PATH`
Path to the SQLite database file.

### `AEGIS_HOST`
Host address for the server.

### `AEGIS_PORT`
Port used by the server.

### `AEGIS_LOG_LEVEL`
Logging verbosity.

### `AEGIS_DEFAULT_MODEL`
Default logical model name exposed by the gateway.

---

## 3. Provider Variables

For NVIDIA pool members, the preferred approach is to store provider credentials in the database or secure config storage, not directly in code.

If environment-based provider bootstrap is needed for development, variables can be defined in the form:

- `AEGIS_NVIDIA_1_API_KEY`
- `AEGIS_NVIDIA_1_LABEL`
- `AEGIS_NVIDIA_2_API_KEY`
- `AEGIS_NVIDIA_2_LABEL`

But database-backed configuration is preferred for the actual product flow.

---

## 4. Runtime Variables

### `AEGIS_SCHEDULER_MODE`
Defines the routing strategy. Example values:
- `health-first`
- `least-busy`
- `round-robin`

### `AEGIS_RETRY_COUNT`
Maximum retry attempts.

### `AEGIS_TIMEOUT_SECONDS`
Request timeout duration.

### `AEGIS_STREAMING_ENABLED`
Enables or disables streaming.

### `AEGIS_THINKING_ENABLED`
Enables or disables thinking support.

### `AEGIS_MAX_REQUEST_SIZE_MB`
Maximum request body size.

---

## 5. Recommended Defaults

- `AEGIS_PORT=8000`
- `AEGIS_LOG_LEVEL=INFO`
- `AEGIS_SCHEDULER_MODE=health-first`
- `AEGIS_RETRY_COUNT=2`
- `AEGIS_TIMEOUT_SECONDS=60`
- `AEGIS_STREAMING_ENABLED=true`
- `AEGIS_THINKING_ENABLED=true`
- `AEGIS_MAX_REQUEST_SIZE_MB=10`

---

## 6. Validation Rules

At startup, AEGIS should verify:
- required variables are present
- numeric values are valid
- booleans are parseable
- database path is writable
- encryption key is present if encrypted storage is enabled

---

## 7. Environment Loading Rules

- use `uv` for local project execution
- load environment variables early in startup
- fail fast on missing critical settings
- keep defaults explicit and documented

---

## 8. Security Note

Secrets should be kept out of source code and out of logs. Environment variables are acceptable for bootstrap and local development, but production should use a secure secret source when available.
