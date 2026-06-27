# RouteFlow

> **Intelligent AI Gateway**

RouteFlow is a self-hosted AI gateway designed to provide a stable, Claude Code-compatible interface while managing provider routing, runtime policies, streaming, and provider pooling behind the scenes.

> **Version:** V1 (NVIDIA NIM)

---

## Features

- Claude Code compatible gateway
- Anthropic-style API compatibility
- NVIDIA NIM integration
- NVIDIA Provider Pool
- Health-aware request scheduling
- Automatic failover
- SSE streaming
- Tool call support
- Thinking support
- SQLite configuration storage
- Professional Control Center
- Provider-agnostic internal architecture

---

## Tech Stack

Backend:
- Python 3.12+
- FastAPI
- HTTPX
- Pydantic
- SQLite
- Uvicorn

Development:
- uv
- pytest
- pytest-asyncio
- ruff

---

## Project Documentation

Read these files before contributing:

1. PROJECT_CONTEXT.md
2. ARCHITECTURE.md
3. IMPLEMENTATION_PLAN.md
4. UI_GUIDELINES.md
5. AGENTS.md

---

## Repository Structure

```text
routeflow/
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
```

---

## Development Philosophy

- Architecture first
- Small, focused modules
- Provider-agnostic core
- NVIDIA-only for V1
- Minimal dependencies
- Production-minded design

---

## Setup (Planned)

```bash
uv init
uv python install 3.12
uv venv
uv sync
uv run uvicorn routeflow.main:app --reload
```

---

## Roadmap

### V1
- NVIDIA NIM
- Provider Pool
- Runtime
- Streaming
- Control Center

### Future
- Multi-provider support
- Plugin system
- Advanced routing
- Enhanced analytics

---

## License

To be decided.

---

## Project Identity

**Name:** RouteFlow

**Tagline:** Intelligent AI Gateway
