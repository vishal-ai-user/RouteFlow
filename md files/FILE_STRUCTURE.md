# AEGIS File Structure

## 1. Purpose

This document defines the expected repository structure for AEGIS.

The goal is to keep the codebase clean, layered, and easy to extend.

---

## 2. Top-Level Structure

```text
aegis/
  api/
  auth/
  config/
  core/
  persistence/
  providers/
  runtime/
  stream/
  translator/
  ui/
  utils/
  main.py
tests/
AGENTS.md
ARCHITECTURE.md
DATABASE_SCHEMA.md
IMPLEMENTATION_PLAN.md
PROJECT_CONTEXT.md
README.md
UI_GUIDELINES.md
API_SPEC.md
CODING_STANDARDS.md
SECURITY.md
TESTING_STRATEGY.md
pyproject.toml
```

---

## 3. Folder Responsibilities

### `api/`
HTTP route handlers and endpoint orchestration.

### `auth/`
Auth token validation and access control.

### `config/`
Environment loading, settings definitions, config validation.

### `core/`
Shared data models, enums, constants, and common helpers.

### `persistence/`
SQLite access, repositories, storage utilities, schema support.

### `providers/`
Provider interfaces and NVIDIA adapter code.

### `runtime/`
Scheduler, routing, retry, cooldown, and failover logic.

### `stream/`
SSE event conversion and streaming output utilities.

### `translator/`
Protocol translation between client payloads and internal models.

### `ui/`
AEGIS Control Center frontend and UI assets.

### `utils/`
Generic utility helpers that do not belong to a domain layer.

### `tests/`
Unit and integration tests.

---

## 4. Suggested Internal Organization

### `api/`
- `routes.py`
- `health.py`
- `messages.py`
- `models.py`

### `auth/`
- `tokens.py`
- `guards.py`

### `config/`
- `settings.py`
- `loader.py`
- `defaults.py`

### `core/`
- `schemas.py`
- `enums.py`
- `errors.py`
- `logging.py`

### `persistence/`
- `db.py`
- `repositories.py`
- `migrations.py`

### `providers/`
- `base.py`
- `nvidia.py`
- `pool.py`

### `runtime/`
- `scheduler.py`
- `router.py`
- `retry.py`
- `health.py`

### `stream/`
- `events.py`
- `writer.py`
- `normalizer.py`

### `translator/`
- `request.py`
- `response.py`
- `claude.py`

### `ui/`
- `dashboard/`
- `components/`
- `styles/`

---

## 5. Naming Rules

- use lowercase module names
- use singular names for stateless utilities
- use descriptive filenames
- avoid vague names like `helpers.py` unless the contents are truly generic

---

## 6. Structure Rules

- keep each layer separated
- keep provider-specific code out of gateway modules
- keep UI assets out of backend modules
- keep database logic out of API handlers
- keep runtime logic out of UI code

---

## 7. Growth Strategy

The structure should allow future additions such as:
- plugin system
- additional providers
- observability modules
- advanced control center pages
- future scheduling strategies

The current layout should make those additions straightforward.
