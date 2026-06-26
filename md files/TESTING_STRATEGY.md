# AEGIS Testing Strategy

## 1. Purpose

This document defines how AEGIS should be tested.

The goal is to make the gateway stable, predictable, and safe to extend.

---

## 2. Testing Goals

Tests should prove that:
- the gateway accepts valid requests
- invalid requests fail cleanly
- translation works correctly
- provider routing works correctly
- streaming works correctly
- failover works correctly
- persistence works correctly
- UI state is consistent where relevant

---

## 3. Test Layers

## 3.1 Unit tests
Test small functions and modules in isolation.

Examples:
- scheduler decision logic
- retry logic
- cooldown logic
- translation helpers
- error mapping

## 3.2 Integration tests
Test how modules work together.

Examples:
- API to translator to runtime flow
- provider pool selection to adapter call
- SQLite persistence round trips

## 3.3 Streaming tests
Test SSE output and event ordering.

Examples:
- start/delta/stop sequence
- provider chunk normalization
- stream error handling

## 3.4 Contract tests
Test request and response schemas against expected API shapes.

Examples:
- `/v1/messages`
- `/v1/models`
- `/v1/messages/count_tokens`

---

## 4. What Must Be Tested

### Gateway
- auth success
- auth failure
- request validation
- error response format

### Translator
- Claude-style request normalization
- response conversion
- thinking block normalization
- tool call normalization

### Runtime
- provider selection
- least-busy choice
- cooldown handling
- failover decision
- retry limits

### Provider layer
- request construction
- error mapping
- stream handling
- timeouts

### Persistence
- settings save/load
- provider member save/load
- logs save/load

### UI
- dashboard load
- provider pool status display
- error/success styles
- responsive behavior

---

## 5. Recommended Tooling

- `pytest`
- `pytest-asyncio`
- `httpx` test client
- `ruff`
- optional snapshot testing if the UI grows more complex

---

## 6. Test Naming

Use names that explain behavior.

Examples:
- `test_rejects_invalid_auth_token`
- `test_selects_least_busy_provider`
- `test_stream_emits_message_stop`
- `test_saves_provider_member_state`

---

## 7. Test Data Rules

- keep test data minimal
- avoid real secrets
- avoid live provider calls in unit tests
- mock external NVIDIA calls in CI unless a separate integration suite is intentionally created

---

## 8. CI Recommendation

A basic CI pipeline should:
1. install dependencies with uv
2. run lint checks
3. run unit tests
4. run integration tests if configured
5. verify formatting

---

## 9. Release Readiness

A milestone is ready only when:
- tests pass
- streaming is valid
- failure paths are covered
- no secrets are exposed
- core architecture remains intact
