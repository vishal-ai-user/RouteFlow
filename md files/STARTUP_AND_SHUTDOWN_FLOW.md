# AEGIS Startup and Shutdown Flow

## 1. Purpose

This document defines the recommended server startup and shutdown behavior for AEGIS.

---

## 2. Startup Goals

AEGIS should start in a predictable order so that:
- config is loaded early
- secrets are validated early
- SQLite is ready before routing begins
- provider pool state is available before traffic starts
- the Control Center reflects real status
- the gateway only begins accepting requests when the core services are ready

---

## 3. Startup Flow

### Recommended order

```text
Process start
  ↓
Load environment variables
  ↓
Load settings and validate config
  ↓
Open SQLite database
  ↓
Run schema/migration checks
  ↓
Load provider members
  ↓
Validate provider credentials
  ↓
Warm up runtime state
  ↓
Initialize FastAPI app
  ↓
Register routes and middleware
  ↓
Mount Control Center UI
  ↓
Start server
  ↓
Begin accepting requests
```

---

## 4. Startup Rules

- fail fast on invalid config
- do not start partial service if required values are missing
- do not accept traffic before auth and routing services are ready
- load pool state before exposing the status endpoints
- initialize logging before any request traffic

---

## 5. Health Readiness

AEGIS should distinguish between:
- **liveness**: the process is running
- **readiness**: the system is ready to serve requests

### Suggested behavior
- `/health` can be used for liveness
- `/status` or a readiness-style endpoint can be used for readiness

---

## 6. Shutdown Goals

AEGIS should shut down cleanly so that:
- active streaming responses are not cut off abruptly when avoidable
- pending logs are flushed
- runtime state is saved
- the database is closed safely
- provider state is persisted if needed

---

## 7. Shutdown Flow

```text
Stop accepting new requests
  ↓
Allow active requests to complete or timeout
  ↓
Close or finalize open streams
  ↓
Flush logs and state
  ↓
Persist provider metadata
  ↓
Close database connection
  ↓
Shutdown complete
```

---

## 8. Stream Shutdown Rules

If streaming responses are active during shutdown:
- try to end them gracefully
- emit a final structured error only if the connection must be terminated
- avoid leaving clients with silent disconnects when possible

---

## 9. State Persistence Rules

Before shutdown, AEGIS may persist:
- provider health snapshots
- cooldown timestamps
- runtime settings
- non-sensitive logs
- last known service state

Do not persist:
- raw API keys in plaintext
- temporary request bodies unless explicitly needed
- sensitive client content unless there is a defined logging policy

---

## 10. Failure Handling During Startup

If startup fails:
- log the exact reason
- exit with a clear error
- do not continue in a half-initialized state

Examples:
- missing environment variables
- invalid database path
- invalid encryption key
- invalid provider credentials
- broken migration state

---

## 11. Failure Handling During Shutdown

If shutdown is interrupted:
- prioritize safe exit
- do not corrupt the database
- keep logs readable
- avoid partial persistence if it would damage state integrity

---

## 12. Final Rule

Startup and shutdown should be deterministic, observable, and boring. That is the goal.
