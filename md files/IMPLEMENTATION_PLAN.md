# AEGIS Implementation Plan

## 1. Build Strategy

AEGIS should be implemented in carefully separated milestones. The first version must stay focused on reliability, compatibility, and a clean foundation.

### Core strategy
- start with a minimal but production-minded backend
- keep NVIDIA as the only external provider in V1
- build a provider-agnostic core so future providers can be added later
- keep the UI separate from gateway logic
- use UV for environment and dependency management
- avoid unnecessary third-party packages

---

## 2. Recommended Tech Stack

### Backend
- **Python**: 3.12 or newer
- **FastAPI**: HTTP API layer
- **Uvicorn**: ASGI server for local and production use
- **Pydantic**: request/response validation
- **Pydantic Settings**: environment-based configuration
- **HTTPX**: async HTTP client for NVIDIA API calls
- **SQLite**: lightweight persistence for settings and runtime state

### UI
- **Frontend**: can start as a simple web dashboard
- **CSS/JS**: clean responsive UI
- **No heavy frontend framework in V1 unless clearly needed**

### Tooling
- **uv**: project and environment management
- **pytest**: tests
- **pytest-asyncio**: async test support
- **ruff**: linting and formatting
- **mypy**: optional type checking if needed later

---

## 3. Dependency Philosophy

AEGIS should keep dependencies small.

### Keep
Use packages that directly support the gateway, runtime, validation, async I/O, testing, or configuration.

### Avoid for V1
- unnecessary framework layers
- large ORMs unless persistence grows beyond SQLite
- heavy state management libraries
- frontend frameworks unless the UI absolutely needs them
- extra streaming libraries if standard FastAPI streaming is enough

### Why this matters
A smaller dependency surface makes the project:
- easier to install
- easier to debug
- easier to secure
- easier to maintain
- faster to understand for AI coding agents

---

## 4. UV Environment Plan

AEGIS should use `uv` as the primary development environment tool.

### Why uv
`uv` is a very fast Python package and project manager. It is well suited for creating and managing isolated Python projects, installing dependencies, and running commands inside the project environment. It also supports project workflows such as syncing dependencies and running commands inside the virtual environment. [uv docs](https://docs.astral.sh/uv/)

### Recommended workflow
1. install Python with uv if needed
2. create the project environment with uv
3. add dependencies through uv
4. run the server with `uv run`
5. keep the lockfile committed
6. do not install packages manually outside the project environment unless there is a very specific reason

### Example UV commands
```bash
uv init
uv python install 3.12
uv venv
uv add fastapi uvicorn pydantic pydantic-settings httpx
uv add --dev pytest pytest-asyncio ruff
uv sync
uv run uvicorn aegis.main:app --reload
```

The exact command style can change based on the final repository structure, but the workflow should stay uv-first. [uv docs](https://docs.astral.sh/uv/getting-started/projects/)

---

## 5. Recommended Package List

### 5.1 Required runtime packages

#### `fastapi`
Main API framework for gateway routes, request validation, and streaming endpoints. FastAPI is a modern high-performance web framework based on Python type hints. [FastAPI docs](https://fastapi.tiangolo.com/)

#### `uvicorn`
ASGI server for running the FastAPI application.

#### `pydantic`
Used for typed request and response models.

#### `pydantic-settings`
Used for structured settings and environment-variable loading.

#### `httpx`
Used for async outbound requests to NVIDIA NIM. HTTPX supports both sync and async APIs and is a good fit for an async framework. [HTTPX docs](https://www.python-httpx.org/)

### 5.2 Persistence packages

#### `sqlite3` (standard library)
Use the built-in SQLite module first. No dependency needed.

If async database access becomes necessary later, that can be introduced in a later phase.

### 5.3 Development and test packages

#### `pytest`
Main test framework.

#### `pytest-asyncio`
Async test support for FastAPI and HTTPX code paths.

#### `ruff`
Linting and formatting.

### 5.4 Optional later packages

These should not be added unless there is a clear reason:
- `orjson` for faster JSON handling
- `rich` for improved terminal output
- `aiosqlite` if async SQLite access becomes necessary
- `jinja2` only if server-rendered UI pages need templating
- `pyyaml` only if YAML config files become necessary

---

## 6. Proposed Package Groups

### Core
- fastapi
- uvicorn
- pydantic
- pydantic-settings
- httpx

### Dev
- pytest
- pytest-asyncio
- ruff

### Optional
- rich
- orjson
- aiosqlite

---

## 7. Implementation Milestones

## Milestone 1 — Project foundation
### Goals
- create repository structure
- configure uv environment
- create core settings module
- create base FastAPI app
- create health endpoints
- create logging setup

### Output
A runnable server with a clean project skeleton.

### Acceptance criteria
- project installs through uv
- server starts successfully
- `/health` returns a successful response
- config loads from environment
- code structure is clean and separated

---

## Milestone 2 — Gateway and auth
### Goals
- create Claude-compatible API routes
- add authentication guard
- validate incoming request payloads
- add structured error responses

### Output
A secure request entry layer.

### Acceptance criteria
- invalid auth is rejected
- invalid payloads are rejected
- request flow reaches internal translator cleanly

---

## Milestone 3 — Internal models and translator
### Goals
- define internal request/response models
- normalize Claude-style request input
- prepare provider request conversion layer
- build response translation logic

### Output
A stable protocol conversion pipeline.

### Acceptance criteria
- client payload can be converted into internal models
- internal output can be translated back into Claude-compatible form

---

## Milestone 4 — NVIDIA provider adapter
### Goals
- build NVIDIA request client
- handle standard and streaming responses
- normalize provider errors
- isolate provider-specific code

### Output
A working NVIDIA integration.

### Acceptance criteria
- one NVIDIA account can handle requests
- streaming works end to end
- errors are normalized

---

## Milestone 5 — Provider pool and scheduler
### Goals
- support multiple NVIDIA API keys
- track health and usage per account
- implement least-busy or health-first routing
- implement cooldown and failover

### Output
A resilient NVIDIA pool manager.

### Acceptance criteria
- pool members can be added and disabled
- healthy accounts are preferred
- failures trigger retry or failover

---

## Milestone 6 — Streaming engine
### Goals
- emit Anthropic-compatible SSE
- support message start/delta/stop events
- handle tool and thinking events if present
- keep stream order stable

### Output
A client-compatible streaming path.

### Acceptance criteria
- streaming responses remain valid
- SSE format is consistent
- partial failures are handled cleanly

---

## Milestone 7 — Persistence
### Goals
- store settings in SQLite
- store provider pool configuration
- store runtime state if needed
- keep secrets safe

### Output
A persistent configuration layer.

### Acceptance criteria
- settings survive restart
- runtime state can be loaded back correctly

---

## Milestone 8 — Control Center UI
### Goals
- build dashboard
- build provider pool view
- build runtime/settings pages
- build logs view
- use orange and black theme

### Output
A professional AEGIS Control Center.

### Acceptance criteria
- UI is responsive
- status is readable
- error/success states use correct colors
- layout works on desktop and smaller screens

---

## Milestone 9 — Polish and hardening
### Goals
- improve tests
- improve logs
- improve error handling
- add rate-limit safeguards
- add request tracing
- clean up naming and module boundaries

### Output
A stable release candidate.

### Acceptance criteria
- no obvious architecture leaks
- common failure paths are tested
- code is easy to extend

---

## 8. Suggested Repository Layout

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
pyproject.toml
README.md
AGENTS.md
PROJECT_CONTEXT.md
ARCHITECTURE.md
IMPLEMENTATION_PLAN.md
UI_GUIDELINES.md
```

---

## 9. Development Rules

- use uv for dependency management
- avoid manual environment drift
- keep dependencies intentional
- use typed data models
- keep provider logic isolated
- keep UI and backend concerns separate
- write tests for each milestone
- avoid building features before the foundation is stable

---

## 10. Final Execution Order

1. initialize project with uv
2. create package structure
3. write settings/config layer
4. create FastAPI skeleton
5. implement auth and gateway
6. implement translator
7. implement NVIDIA provider adapter
8. implement pool manager and scheduler
9. implement SSE streaming
10. add SQLite persistence
11. build Control Center UI
12. test and harden
13. prepare for future providers

---

## 11. Final Statement

AEGIS V1 should be small, stable, and focused. The best path is a uv-managed Python project with FastAPI, Pydantic, HTTPX, SQLite, and a minimal dependency footprint. The architecture must stay clean so the NVIDIA-only version can later evolve into a multi-provider gateway without major rewrites.

