# AGENTS.md

## Purpose

This file defines the working rules for AI coding agents operating on the AEGIS repository.

Read order:
1. `PROJECT_CONTEXT.md`
2. `ARCHITECTURE.md`
3. `IMPLEMENTATION_PLAN.md`
4. `UI_GUIDELINES.md`
5. This file

Do not treat this file as architecture documentation. It is only an execution rulebook.

---

## Non-negotiable rules

1. Follow the architecture documents exactly.
2. Do not invent new product scope without approval.
3. Do not add providers beyond NVIDIA in V1.
4. Do not collapse layers or merge responsibilities.
5. Do not place UI logic inside backend gateway code.
6. Do not place provider-specific logic outside provider adapter/pool modules.
7. Do not introduce unnecessary dependencies.
8. Do not refactor for style unless it improves clarity, correctness, or maintainability.
9. Do not leave hidden TODOs or partial implementations.
10. Do not remove or weaken compatibility requirements.

---

## Project scope rules

### V1 scope
- Claude Code-compatible gateway
- Anthropic-style request and response compatibility
- NVIDIA NIM only
- NVIDIA provider pool
- runtime routing and failover
- SSE streaming
- thinking support
- tool call support
- authentication
- SQLite persistence
- AEGIS Control Center UI

### Out of scope for V1
- multi-provider support beyond NVIDIA
- plugin marketplace
- websocket transport
- cluster mode
- enterprise SSO
- billing
- mobile apps
- analytics platform beyond basic dashboard metrics

---

## Architecture rules

### Required layers
- Gateway
- Auth
- Translator
- Runtime
- Provider Pool
- NVIDIA Adapter
- Streaming
- Persistence
- Control Center UI

### Layer discipline
- Gateway only receives and validates HTTP requests.
- Auth only verifies access.
- Translator only converts payloads and responses.
- Runtime only makes routing and retry decisions.
- Provider Pool only manages NVIDIA pool members and their state.
- NVIDIA Adapter only talks to NVIDIA NIM.
- Streaming only converts internal events into SSE output.
- Persistence only stores and retrieves data.
- Control Center only renders and manages UI state.

If a feature crosses layers, split it into smaller functions or modules.

---

## NVIDIA pool rules

- Treat each NVIDIA API key/account as one pool member.
- Track health, active requests, cooldown, last error, and last success per member.
- Prefer healthy, low-load members.
- Fail over to another eligible member when needed.
- Cool down failing members before routing new traffic to them.
- Do not hardcode one key into the request path.

---

## Runtime rules

- Keep routing deterministic where possible.
- Use explicit policy objects or decision functions.
- Avoid hidden side effects.
- Keep retries bounded.
- Keep failover safe and observable.
- Preserve request identity for logs and debugging.
- Do not let runtime logic depend on UI state.

---

## Streaming rules

- Preserve event order.
- Produce valid Anthropic-style SSE.
- Keep stream normalization separate from provider calls.
- Handle partial failures gracefully.
- Do not buffer full responses unless a non-streaming path requires it.
- If a stream cannot be completed, emit a clean structured error.

---

## Configuration rules

- Use `uv` for environment and dependency management.
- Keep the dependency list intentionally small.
- Use environment-driven settings with validation.
- Keep secrets out of source code.
- Do not mix runtime state with static configuration.
- Persist only what must survive restart.

---

## Coding rules

- Use clear names that match the architecture docs.
- Prefer small modules and small functions.
- Use typed models for request/response data.
- Prefer explicit logic over clever logic.
- Keep async code truly async.
- Keep sync code isolated when necessary.
- Make error handling visible and structured.
- Keep logging useful and non-sensitive.

---

## Testing rules

- Add tests for each milestone.
- Test translation, runtime decisions, provider routing, and streaming separately.
- Test failure paths, not just success paths.
- Keep tests deterministic.
- Do not merge untested core logic.

---

## UI rules

- Use the orange/black design system from `UI_GUIDELINES.md`.
- Keep the UI clean, responsive, and minimal.
- Use green for success and red for errors.
- Keep dashboard information scannable.
- Do not overload the interface with unnecessary effects.

---

## Workflow rules

Before coding:
1. identify the milestone
2. identify the affected layers
3. identify the exact files to change
4. keep the change minimal

During coding:
1. preserve existing contracts
2. avoid unrelated refactors
3. keep changes aligned with the architecture
4. update tests if behavior changes

After coding:
1. verify the flow end to end
2. run relevant tests
3. check for architectural drift
4. summarize what changed clearly

---

## Dependency rules

Before adding any new package:
- verify whether the standard library is enough
- verify whether an existing dependency already solves the need
- keep V1 lean
- prefer stable, widely used packages only

If a dependency is optional, defer it unless there is a strong technical reason.

---

## Error-handling rules

- Return structured, actionable errors.
- Never leak secrets in errors.
- Make provider failures visible.
- Make auth failures explicit.
- Make validation failures clear.
- Make streaming failures graceful.

---

## Acceptance standard

A change is acceptable only if it:
- matches the architecture
- fits the V1 scope
- remains easy to understand
- remains easy to test
- does not introduce unnecessary complexity
- does not weaken Claude compatibility

---

## When unsure

If a decision affects architecture, scope, provider strategy, or UI direction, stop and ask for approval before implementing it.
