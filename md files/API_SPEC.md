# AEGIS API Specification

## 1. Purpose

This document defines the external HTTP interface for AEGIS V1.

AEGIS must expose a Claude Code-compatible API while remaining internally provider-agnostic.

---

## 2. Base Principles

- keep request and response shapes explicit
- preserve streaming compatibility
- return structured errors
- keep endpoints minimal in V1
- avoid provider-specific leakage in public API contracts

---

## 3. Authentication

All protected endpoints must require an AEGIS auth token.

### Auth header
```http
Authorization: Bearer <AEGIS_TOKEN>
```

If authentication fails, return a standard unauthorized response.

---

## 4. Endpoints

## 4.1 Health

### `GET /health`
Returns server liveness.

#### Response
```json
{
  "ok": true,
  "service": "aegis",
  "version": "v1"
}
```

---

## 4.2 Status

### `GET /status`
Returns a summary of server and provider pool health.

#### Response
```json
{
  "ok": true,
  "service": "aegis",
  "pool": {
    "total": 2,
    "healthy": 2,
    "disabled": 0
  },
  "runtime": {
    "streaming": true,
    "scheduler": "health-first"
  }
}
```

---

## 4.3 Models

### `GET /v1/models`
Returns the models exposed by the gateway.

#### Response
```json
{
  "data": [
    {
      "id": "claude-compatible-default",
      "type": "model"
    }
  ]
}
```

V1 may return a small logical model set mapped to NVIDIA-backed routing.

---

## 4.4 Count Tokens

### `POST /v1/messages/count_tokens`
Used to estimate token usage for Claude-compatible requests.

#### Request body
```json
{
  "model": "claude-compatible-default",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ]
}
```

#### Response
```json
{
  "input_tokens": 10
}
```

---

## 4.5 Messages

### `POST /v1/messages`
Main Claude Code-compatible chat endpoint.

Supports:
- normal responses
- streaming responses
- system messages
- tools
- thinking blocks

#### Request fields
- `model`
- `messages`
- `system` or `system` messages
- `max_tokens`
- `temperature` if supported by runtime policy
- `stream`
- `tools`
- `tool_choice`
- `thinking`

#### Example request
```json
{
  "model": "claude-compatible-default",
  "messages": [
    {
      "role": "user",
      "content": "Create a simple login page"
    }
  ],
  "max_tokens": 1024,
  "stream": true
}
```

#### Non-streaming response
```json
{
  "id": "msg_001",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "Here is a simple login page..."
    }
  ],
  "model": "claude-compatible-default",
  "stop_reason": "end_turn",
  "usage": {
    "input_tokens": 120,
    "output_tokens": 220
  }
}
```

---

## 5. Streaming Contract

When `stream=true`, the endpoint must return SSE.

### Content-Type
```http
text/event-stream
```

### Event types
- `message_start`
- `content_block_start`
- `content_block_delta`
- `content_block_stop`
- `message_delta`
- `message_stop`
- `error`

### Example event sequence
```text
event: message_start
data: {...}

event: content_block_start
data: {...}

event: content_block_delta
data: {...}

event: content_block_stop
data: {...}

event: message_delta
data: {...}

event: message_stop
data: {...}
```

---

## 6. Error Responses

AEGIS should return structured JSON errors.

### Standard error shape
```json
{
  "error": {
    "type": "validation_error",
    "message": "Invalid request body",
    "request_id": "req_123"
  }
}
```

### Common error types
- `unauthorized`
- `validation_error`
- `provider_error`
- `rate_limited`
- `timeout`
- `stream_error`
- `internal_error`

---

## 7. Future-Compatible Constraints

Even though V1 only uses NVIDIA, the API should remain stable enough to support:
- multiple clients
- future providers
- future routing policies
- future diagnostics endpoints

---

## 8. API Stability Rules

- do not change endpoint names casually
- do not change response envelopes without a version bump
- do not leak internal provider identifiers in public contracts
- keep event order stable for streaming
