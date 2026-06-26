# AEGIS Project Context

## 1. Project Identity

**Project Name:** AEGIS  
**Tagline:** Intelligent AI Gateway

AEGIS is a self-hosted AI gateway that sits between AI clients and model providers. It accepts Claude Code-compatible requests, applies routing and runtime rules, and forwards them to configured providers. For V1, the project uses **NVIDIA NIM only** as the external provider while keeping the architecture provider-agnostic for future expansion.

## 2. Why AEGIS Exists

AEGIS exists to solve a practical problem: AI clients often need a stable, configurable gateway that can handle provider routing, request normalization, streaming, retries, health checks, and centralized control without forcing the client to know the details of each provider.

The project is designed to:
- keep the client experience simple
- centralize provider management
- support Claude Code-compatible workflows
- reduce manual switching between AI endpoints
- make future provider additions easy without rewriting the core server

## 3. Core Vision

AEGIS is not just a proxy. It is an **AI gateway and control plane**.

The long-term vision is to provide:
- a clean request gateway
- a provider pool with health-aware routing
- a runtime engine for policy decisions
- a translation layer for protocol compatibility
- a professional control center UI
- a plugin-ready foundation for future providers and integrations

## 4. V1 Scope

V1 is intentionally focused and should stay narrow.

### Included in V1
- Claude Code-compatible request handling
- Anthropic-style API compatibility
- NVIDIA NIM as the only external provider
- NVIDIA provider pooling
- request scheduling and load balancing
- health tracking and failover
- SSE streaming support
- thinking support
- tool call support
- runtime configuration
- authentication for the gateway
- AEGIS Control Center UI
- logging and basic diagnostics
- SQLite for lightweight persistence

### Not included in V1
- multi-provider support beyond NVIDIA
- plugin marketplace
- advanced analytics platform
- multi-user enterprise access control
- distributed cluster mode
- websocket transport
- complex billing or quota management
- mobile apps

## 5. Target Users

AEGIS is intended for:
- developers building with Claude Code or Claude-compatible clients
- AI power users who want a local or self-hosted gateway
- teams that want centralized provider control
- developers who need routing, failover, or account pooling
- future contributors who want a clean architecture to extend

## 6. Product Principles

AEGIS should always follow these principles:

### 6.1 Clarity over complexity
The system should be easy to understand, easy to debug, and easy to extend.

### 6.2 Stable compatibility
Claude Code compatibility should remain a first-class requirement.

### 6.3 Provider-agnostic core
Even though V1 uses NVIDIA only, the core server should not be tied to NVIDIA-specific logic.

### 6.4 Small, composable modules
Each module should have one job:
- API handling
- request translation
- runtime policy
- provider pooling
- persistence
- UI rendering

### 6.5 Production-minded design
The architecture should be written as if the project will eventually be maintained, extended, and deployed by real teams.

## 7. What AEGIS Is Not

AEGIS is not:
- a toy demo
- a single-file script
- a direct provider wrapper with no structure
- a client replacement for Claude Code
- a UI-only project
- a provider lock-in project

AEGIS should always behave like a proper gateway layer with a clean internal architecture.

## 8. NVIDIA Pool Philosophy

V1 uses NVIDIA NIM only, but it should still be designed as a pool.

That means the server should treat each NVIDIA account or API key as a pool member with:
- its own health state
- its own load state
- its own recent error state
- its own routing eligibility

This allows AEGIS to:
- balance requests across available keys
- retry on failure
- temporarily cool down unhealthy keys
- preserve throughput and stability

## 9. Control Center Philosophy

The UI should be called **AEGIS Control Center**.

The Control Center should feel:
- modern
- clean
- responsive
- smooth
- professional
- minimal
- dashboard-oriented

It should use an orange-and-black visual identity with:
- red for errors
- green for success
- dark surfaces
- clear spacing
- easy-to-scan cards
- simple navigation

## 10. Architecture Direction

The architecture should be built around these major layers:

- **Gateway Layer**: receives client requests
- **Translator Layer**: converts client protocol into internal form and back
- **Runtime Layer**: applies routing, retry, and policy decisions
- **Provider Pool Layer**: manages NVIDIA accounts and health
- **Streaming Layer**: emits SSE responses
- **Persistence Layer**: stores settings, pool state, and logs
- **Control Center Layer**: provides UI for management and visibility

This separation is important because it keeps the system maintainable and makes future provider support much easier.

## 11. Design Goals

AEGIS should be:
- easy to install
- easy to configure
- easy to debug
- easy to extend
- easy to reason about
- robust under failure
- clean in code structure
- consistent in naming and behavior

## 12. Success Criteria for V1

V1 is successful if all of the following are true:
- Claude Code can connect to AEGIS successfully
- requests are forwarded to NVIDIA NIM correctly
- streaming responses work reliably
- provider pooling and failover work
- the Control Center can show status and settings
- runtime configuration persists correctly
- logs are readable and useful
- the codebase remains modular and understandable

## 13. Future Vision

After V1, AEGIS can grow into:
- multi-provider support
- plugin-based provider integrations
- advanced routing policies
- richer analytics
- role-based access control
- team collaboration features
- remote control center deployment
- metrics and observability integrations

The core architecture should be strong enough that these additions can happen without rewriting the system.

## 14. Terminology

To keep the project consistent, use these names:

- **AEGIS** — the project name
- **AEGIS Control Center** — the admin/dashboard UI
- **Gateway** — the HTTP entry layer
- **Runtime** — policy and routing decision layer
- **Provider Pool** — a group of NVIDIA accounts/API keys
- **Translator** — protocol conversion layer
- **Streaming Engine** — SSE output layer
- **Health Monitor** — provider status and failover logic

## 15. Final Statement

AEGIS should feel like a serious AI infrastructure product, not a quick hack.  
The first version must stay focused on NVIDIA only, while preserving a clean path toward future providers and features.

