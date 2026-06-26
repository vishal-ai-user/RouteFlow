# AEGIS Model Mapping

## 1. Purpose

This document defines how AEGIS maps Claude-compatible model identifiers to NVIDIA NIM model identifiers.

---

## 2. Design Principles

- keep mapping explicit
- keep mapping configurable
- keep gateway input stable
- keep provider model ids isolated from clients
- allow future updates without redesigning the protocol layer

---

## 3. Mapping Concept

Claude Code and Claude-compatible clients may send model ids that are meaningful at the client layer, while NVIDIA NIM requires its own model ids.

AEGIS sits between them and translates the model choice.

### Flow

```text
Client model id
      ↓
AEGIS model mapping
      ↓
NVIDIA model id
      ↓
NVIDIA NIM request
```

---

## 4. V1 Mapping Strategy

For V1, the mapping should be stored in configuration and loaded at startup.

### Recommended mapping groups
- `default`
- `sonnet`
- `opus`
- `haiku`

Even if only one or two targets are used at first, keeping the structure grouped by Claude family makes future expansion easier.

---

## 5. Example Mapping Shape

```json
{
  "default": "nvidia-model-default",
  "sonnet": "nvidia-model-sonnet",
  "opus": "nvidia-model-opus",
  "haiku": "nvidia-model-haiku"
}
```

The exact NVIDIA ids can be changed later without changing the architecture.

---

## 6. Mapping Rules

- unknown client model ids should fall back to the configured default if allowed by policy
- if fallback is not allowed, return a structured validation error
- do not expose NVIDIA model ids in public API responses unless needed for admin diagnostics
- keep mapping logic inside the translator or runtime config layer, not in the gateway route handlers

---

## 7. Runtime Decision Order

The recommended order is:
1. read incoming model id
2. resolve through model mapping
3. resolve provider pool member
4. call NVIDIA adapter with the mapped NVIDIA model id

---

## 8. Configurable Behavior

The mapping should support:
- default model
- family-based mapping
- manual overrides
- future per-client policy if needed

---

## 9. Validation Rules

At startup:
- verify that the default mapping exists
- verify that all required families resolve correctly
- warn if a mapped model id is empty or invalid

---

## 10. Future Expansion

Later versions may support:
- multiple providers per model family
- routing based on cost
- routing based on latency
- routing based on availability
- user-specific model preferences
