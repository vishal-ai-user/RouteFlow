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
- Professional Dashboard & Server UI
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

## Getting Started

Follow these step-by-step instructions to get your **RouteFlow Server** running locally:

### Prerequisites
1. **Python 3.12 or higher** installed on your system.
2. **uv** (an extremely fast Python package and environment manager).
   - **Windows (Powershell)**:
     ```powershell
     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
     ```
   - **macOS/Linux**:
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```

### Setup Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/vishal-ai-user/RouteFlow.git
   cd RouteFlow
   ```

2. **Install Dependencies**:
   Use `uv` to automatically create a virtual environment and install all dependencies:
   ```bash
   uv sync
   ```

3. **Configure Environment Variables**:
   Copy the environment template file:
   - **Windows**:
     ```powershell
     copy .env.example .env
     ```
   - **macOS/Linux**:
     ```bash
     cp .env.example .env
     ```

4. **Set your Credentials & API Keys**:
   Open the newly created `.env` file in a text editor and configure your variables:
   - **`ROUTEFLOW_AUTH_TOKEN`**: A secure secret token of your choice. You will use this token to sign in to the Server UI and authorize downstream client requests.
   - **NVIDIA NIM API Keys**: Add your NVIDIA NIM API keys (e.g., `ROUTEFLOW_NVIDIA_1_API_KEY=nvapi-...`) and labels to register your account pool.

5. **Run the RouteFlow Server**:
   Start the server by running:
   ```bash
   uv run python -m routeflow.main
   ```
   *The server will start on `http://localhost:8000`. On first run, it automatically creates the local SQLite database (`routeflow.db`) and executes all database table migrations.*

---

## Accessing the Server Dashboard

1. Open your browser and navigate to: **`http://localhost:8000/ui/`**
2. Enter your configured **`ROUTEFLOW_AUTH_TOKEN`** in the authentication screen to sign in.
3. Use the dashboard to register provider account keys, set up model translations, view real-time request logs, track error history, and monitor performance analytics.

---

## Running Tests

To verify that the server components, translator, stream handlers, and provider pools are fully functional:
```bash
uv run pytest
```

---

## Project Documentation

Refer to [AGENTS.md](file:///c:/Users/VISHAL/Desktop/AEGIS/AGENTS.md) for AI coding agent guidelines, layer constraints, and development workflow policies.

---

## Repository Structure

```text
routeflow/
  api/          # HTTP routes, middlewares, validation schemas
  auth/         # Authentication guards, token verifications
  config/       # Settings parsing and environment loading
  core/         # Logging structures, exception classes, shared models
  persistence/  # SQLite migrations, DB connect, SQL repositories
  providers/    # NVIDIA adapters and pool members tracking
  runtime/      # Schedulers, retries, and failover router
  stream/       # SSE formatter, response chunk normalizers
  translator/   # Anthropic-to-NVIDIA payload translations
  ui/           # Front-end HTML/CSS/JS Single Page Application
  utils/        # Common developer utilities
  main.py       # FastAPI app creation & entry point
tests/          # Comprehensive pytest suite
```

---

## Project Identity

- **Name:** RouteFlow
- **Tagline:** Intelligent AI Gateway
