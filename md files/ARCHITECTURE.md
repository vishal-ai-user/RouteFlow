# AEGIS Architecture

## 1. Architecture Summary

AEGIS is an AI gateway that receives Claude Code-compatible requests, applies runtime rules, routes traffic through a provider pool, and returns Anthropic-style streaming responses back to the client.

For V1, AEGIS uses **NVIDIA NIM only** as the external provider, but the internal architecture must remain provider-agnostic so future providers can be added without redesigning the core server.

### High-level flow

```text
Claude Code / Compatible Client
            ↓
        Gateway API
            ↓
     Request Translator
            ↓
         Runtime Engine
            ↓
      NVIDIA Provider Pool
            ↓
        NVIDIA NIM API
            ↓
      Streaming Normalizer
            ↓
     Anthropic-compatible SSE
            ↓
Claude Code / Compatible Client
```

---

## 2. Architectural Goals

AEGIS must:
- expose a stable Claude Code-compatible gateway
- normalize requests into an internal request model
- route requests across a pool of NVIDIA API keys
- monitor health and load per provider key
- retry safely on failure
- stream output using Anthropic-style SSE events
- preserve a clean path for future provider plugins
- keep configuration and runtime decisions separate
- provide a control center for observability and management

---

## 3. Core Design Principles

### 3.1 Separation of concerns
Each layer should do one thing only.

### 3.2 Provider-agnostic core
The server logic must not depend on NVIDIA-specific behavior outside the provider adapter layer.

### 3.3 Compatibility first
Client compatibility must remain stable even if providers or routing strategies change.

### 3.4 Stream-first design
The system should treat streaming as a first-class behavior, not a special case.

### 3.5 Failure-aware routing
The runtime must assume provider failures can happen and route accordingly.

### 3.6 Small modules
The codebase should remain modular and easy to reason about.

---

## 4. System Layers

AEGIS is split into the following layers:

1. **Gateway Layer**
2. **Authentication Layer**
3. **Translation Layer**
4. **Runtime Layer**
5. **Provider Pool Layer**
6. **Provider Adapter Layer**
7. **Streaming Layer**
8. **Persistence Layer**
9. **Control Center Layer**

---

## 5. Gateway Layer

The Gateway Layer receives all incoming requests.

### Responsibilities
- expose Claude Code-compatible endpoints
- validate basic request shape
- forward requests into internal services
- return structured errors
- support streaming and non-streaming responses
- keep HTTP handling isolated from business logic

### Expected endpoints
- `POST /v1/messages`
- `POST /v1/messages/count_tokens`
- `GET /v1/models`
- `GET /health`
- `GET /status`

### Gateway rules
- the gateway must not contain provider logic
- the gateway must not perform load balancing
- the gateway must not inspect provider-specific fields beyond validation
- the gateway should only coordinate request flow

---

## 6. Authentication Layer

Authentication protects the gateway from unauthorized use.

### Responsibilities
- verify API tokens or gateway tokens
- reject invalid requests before processing
- attach request identity to logs
- support future user/session expansion if needed

### Rules
- authentication must happen early
- failed authentication should stop processing immediately
- auth logic should be reusable by API and control center endpoints

---

## 7. Translation Layer

The Translation Layer converts between external client payloads and the internal AEGIS request model.

### Why this layer exists
Different clients and providers use different payload formats. AEGIS needs one internal representation so the rest of the system can stay stable.

### Responsibilities
- parse Claude-compatible input
- normalize message history
- normalize system prompts
- normalize tools and tool calls
- normalize thinking/reasoning hints
- normalize stream preferences
- convert internal responses back to Anthropic-style output

### Internal translation direction

```text
Client Payload
      ↓
Internal Request Model
      ↓
Provider Payload
      ↓
Provider Response
      ↓
Internal Response Model
      ↓
Client-Compatible SSE/JSON
```

### Rules
- translation must not contain routing policy
- translation must not know pool health
- translation must not know about UI concerns

---

## 8. Runtime Layer

The Runtime Layer is the decision engine.

### Responsibilities
- choose which NVIDIA pool member should handle the request
- apply load balancing strategy
- apply failover strategy
- apply retry strategy
- apply cooldown logic
- apply timeout policy
- apply stream policy
- apply request shaping rules
- keep per-request decisions isolated and testable

### Runtime inputs
- request size
- request type
- stream flag
- current pool health
- active request count
- recent error state
- cooldown state
- retry history

### Runtime outputs
- selected provider pool member
- retry decision
- backoff decision
- failover decision
- final response policy

### Runtime rules
- runtime should be deterministic where possible
- runtime should be easy to test
- runtime should not talk directly to the UI
- runtime should not store raw request payloads unless needed for logs or persistence

---

## 9. Provider Pool Layer

The Provider Pool is a managed collection of NVIDIA API keys/accounts.

### Responsibilities
- store all configured NVIDIA accounts
- track per-account health
- track current load
- track last error
- track last success
- track cooldown periods
- expose eligible providers to the runtime

### Pool member concept
Each NVIDIA account/API key is treated as one pool member.

### Pool member fields
- `name`
- `api_key`
- `email_label` or display label
- `enabled`
- `healthy`
- `active_requests`
- `recent_errors`
- `cooldown_until`
- `last_used_at`
- `last_success_at`
- `last_error_at`
- `rpm_window_usage`

### Pool rules
- a disabled account must never receive traffic
- a cooling account should be skipped until eligible again
- a failing account should be deprioritized
- a healthy low-load account should be preferred

---

## 10. Provider Adapter Layer

The Provider Adapter Layer talks to NVIDIA NIM.

### Responsibilities
- build NVIDIA request payloads
- attach NVIDIA API credentials
- send request or stream request
- normalize NVIDIA errors
- normalize NVIDIA stream chunks
- map NVIDIA response fields to internal response objects

### Rules
- the adapter must be isolated from gateway code
- the adapter must not contain runtime selection logic
- the adapter should be reusable across provider pool members if their request shape is identical

### V1 provider assumption
In V1, all external provider activity goes through NVIDIA NIM only.

---

## 11. Streaming Layer

Streaming is a core AEGIS capability.

### Responsibilities
- receive stream chunks from NVIDIA
- convert chunks into internal events
- emit Anthropic-style SSE events
- preserve ordering
- handle finish events
- handle tool-call events
- handle thinking blocks if supported
- recover gracefully from mid-stream errors

### Typical stream event sequence

```text
message_start
content_block_start
content_block_delta
content_block_delta
content_block_stop
message_delta
message_stop
```

### Streaming rules
- stream ordering must be preserved
- partial failures must be handled cleanly
- the client should receive valid SSE even when errors happen mid-flight
- stream conversion logic should be separate from provider request logic

---

## 12. Persistence Layer

The Persistence Layer stores configuration and runtime metadata.

### Responsibilities
- store provider pool configuration
- store runtime settings
- store auth settings
- store logs or diagnostics metadata
- store UI settings if needed
- store cooldown or state snapshots if necessary

### V1 persistence choice
Use **SQLite** for simplicity and portability.

### Persistence rules
- persistence should not be required for every single request path
- critical runtime operations should remain fast
- persistence writes should be batched or minimized where possible

---

## 13. Control Center Layer

The Control Center is the administrative UI for AEGIS.

### Name
**AEGIS Control Center**

### Responsibilities
- show server status
- show pool health
- show account load
- show recent errors
- allow config edits
- allow provider enabling/disabling
- allow runtime tuning
- provide logs and diagnostics
- support visual confirmation that the gateway is healthy

### UI pages
- Dashboard
- Provider Pool
- Runtime
- Analytics
- Logs
- Settings

### UI principles
- clean
- responsive
- smooth
- minimal
- professional
- orange and black themed
- red for errors
- green for success

---

## 14. Request Lifecycle

### 14.1 Standard request path

```text
Client
  ↓
Gateway
  ↓
Auth
  ↓
Translator
  ↓
Runtime
  ↓
Provider Pool
  ↓
Provider Adapter
  ↓
NVIDIA NIM
  ↓
Provider Response
  ↓
Streaming Layer / Response Normalizer
  ↓
Client
```

### 14.2 Streaming request path

```text
Client stream request
  ↓
Gateway
  ↓
Auth
  ↓
Translator
  ↓
Runtime
  ↓
Pool selection
  ↓
NVIDIA stream request
  ↓
Stream chunk normalization
  ↓
Anthropic SSE writer
  ↓
Client
```

---

## 15. Scheduling and Load Balancing

AEGIS should support pool-aware scheduling.

### Recommended scheduling order
1. prefer healthy accounts
2. prefer low active-request count
3. prefer accounts not in cooldown
4. prefer accounts with lower recent error rate
5. fall back to the best available account

### Candidate strategies
- Round Robin
- Least Busy
- Health-First
- Weighted Least Load
- Cooldown-aware selection

### V1 recommendation
Use **Health-First + Least Busy**.

This gives good stability without making the scheduler too complex.

---

## 16. Retry and Failover

### Retry rules
- retry only when it is safe
- do not retry indefinitely
- retry on transient failures
- stop retrying on permanent auth/config failures

### Failover rules
- if one account fails, try another eligible pool member
- if all accounts fail, return a structured error
- do not create retry storms
- apply backoff when repeated failures happen

### Key principle
Failover should improve reliability, not hide systematic misconfiguration.

---

## 17. Error Handling

AEGIS must produce clear and structured errors.

### Error categories
- authentication errors
- validation errors
- provider errors
- timeout errors
- rate limit errors
- stream errors
- config errors
- internal server errors

### Error rules
- errors should be human-readable
- errors should be useful in logs
- error responses should be consistent
- error styling in UI should use red theme

---

## 18. Logging and Observability

### Logging goals
- trace a request from entry to exit
- record pool selection decisions
- record failures and retries
- record latency and provider usage
- support debugging from the Control Center

### Log content
- request id
- timestamp
- selected pool member
- runtime decision
- provider latency
- retry attempts
- final status
- error message if any

### Logging rules
- logs should be structured
- logs should not leak secrets
- logs should be easy to read from the UI

---

## 19. Folder Structure Philosophy

The codebase should remain organized by responsibility.

### Recommended top-level layout

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
```

### Layer meanings
- `api/` for HTTP route handling
- `auth/` for authentication
- `config/` for configuration loading and validation
- `core/` for shared models and shared helpers
- `persistence/` for SQLite and state storage
- `providers/` for NVIDIA adapter and future provider interfaces
- `runtime/` for scheduling and routing decisions
- `stream/` for SSE event conversion
- `translator/` for protocol conversion
- `ui/` for the Control Center
- `utils/` for general utilities

---

## 20. Data Models

AEGIS should use explicit internal models.

### Suggested core models
- `GatewayRequest`
- `InternalRequest`
- `PoolMember`
- `RuntimeDecision`
- `ProviderResult`
- `StreamEvent`
- `GatewayResponse`
- `SystemConfig`
- `RuntimeConfig`
- `AuthConfig`

### Model rules
- models should be typed
- models should be shared across layers when appropriate
- models should avoid provider-specific leakage

---

## 21. Security Principles

### Security rules
- never log raw API keys
- never expose provider secrets in UI
- validate all external inputs
- reject malformed payloads early
- keep auth separate from provider logic
- avoid unsafe dynamic execution
- keep config values explicit and validated

---

## 22. Non-goals for V1

The following are not part of V1:
- distributed multi-node scheduling
- enterprise SSO
- advanced billing systems
- plugin marketplace
- multi-provider support beyond NVIDIA
- websocket streaming
- complicated analytics pipeline

---

## 23. Future Expansion Path

AEGIS should be ready to evolve into:
- multi-provider gateway
- plugin-based provider system
- advanced routing policies
- remote monitoring
- richer dashboards
- multi-user control center
- team collaboration
- observability integrations
- automatic provider discovery

The core architecture must support these future additions without rewriting the gateway.

---

## 24. Architectural Constraints

To keep AEGIS maintainable:
- do not mix UI logic with runtime logic
- do not mix provider selection with translation logic
- do not mix persistence with request handling
- do not hardcode configuration in business logic
- do not let provider-specific code leak into the gateway layer
- do not create large “god” modules

---

## 25. Final Architectural Statement

AEGIS should behave like a serious AI infrastructure product.

The architecture must be:
- stable for Claude Code-compatible requests
- focused on NVIDIA in V1
- cleanly layered
- stream-aware
- pool-aware
- future-proof
- easy to maintain
- easy to extend

