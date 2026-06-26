# NVIDIA NIM Reference

## 1. Purpose

This document captures the NVIDIA NIM assumptions and integration contract used by AEGIS V1.

AEGIS V1 uses NVIDIA NIM as the only external model provider, so the adapter layer needs a clear reference for request shape, auth, streaming, and error handling.

---

## 2. Integration Assumptions

For V1, AEGIS should treat NVIDIA NIM as an HTTP-based model service with:
- token-based authentication
- request/response payloads that are compatible with an OpenAI-style chat API or a close equivalent
- streaming support for token-by-token or chunk-by-chunk output
- structured error responses
- model identifiers that are different from Claude model identifiers

If NVIDIA changes the contract in the future, the adapter should remain isolated so the rest of AEGIS does not need to change.

---

## 3. Adapter Responsibilities

The NVIDIA adapter should:
- build outbound requests for NVIDIA NIM
- attach the correct API key
- send normal and streaming requests
- normalize provider errors
- convert provider output into AEGIS internal response models
- expose health checks for each pool member
- keep NVIDIA-specific behavior out of the gateway and runtime layers

---

## 4. Request Contract

### Required request data
The adapter should support:
- model id
- message list
- system prompt or equivalent system content
- streaming flag
- max token limit
- temperature or similar sampling controls if supported
- tool call payloads if supported
- thinking-related payloads if supported

### Internal expectation
AEGIS should not assume that NVIDIA uses Claude-native request fields. The translator layer should normalize external input before the adapter receives it.

---

## 5. Authentication Contract

The adapter should use a secret API key per NVIDIA pool member.

### Rules
- never log the raw API key
- never expose the raw API key in the UI
- keep the key inside the pool member record or secret storage
- allow multiple NVIDIA keys to coexist in the pool

---

## 6. Streaming Contract

The adapter must support streaming in a way that AEGIS can normalize into Anthropic-style SSE.

### Required stream behavior
- preserve order
- forward partial chunks
- surface errors cleanly
- allow the stream layer to convert provider chunks into client-facing events

### Expected stream normalization target
AEGIS should convert provider output into:
- message start
- content block start
- content block delta
- content block stop
- message delta
- message stop
- error events when needed

---

## 7. Health and Eligibility Contract

Each NVIDIA pool member should be treated as a separate operational unit.

### A member should be considered eligible when:
- it is enabled
- it is not in cooldown
- it is marked healthy
- it has not exceeded local routing constraints

### A member should be deprioritized or skipped when:
- it is disabled
- it is in cooldown
- it has failed recently
- it has excessive active load
- it is otherwise unhealthy

---

## 8. Error Handling Expectations

The adapter should normalize errors into categories such as:
- authentication failure
- invalid model
- rate limit
- timeout
- upstream unavailable
- stream interruption
- unexpected provider error

### Rules
- do not leak provider secrets in error messages
- do not return raw provider stack traces
- keep error messages actionable for the runtime layer

---

## 9. Model Behavior Notes

V1 should treat NVIDIA model ids as implementation details behind AEGIS model mapping.

### This means:
- Claude model names are accepted at the gateway boundary
- AEGIS maps them to NVIDIA model ids
- the adapter only sees the mapped NVIDIA id
- the provider response is converted back into the AEGIS contract

---

## 10. Future Compatibility

This reference is intentionally NVIDIA-specific for V1.

If AEGIS adds additional providers later, those providers should use the same adapter pattern and remain isolated from the gateway and translator layers.
