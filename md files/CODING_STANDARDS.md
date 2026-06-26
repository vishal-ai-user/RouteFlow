# AEGIS Coding Standards

## 1. Purpose

This document defines the coding style and engineering rules for the AEGIS repository.

---

## 2. Core Rules

- write clear, typed Python
- keep functions small and focused
- keep modules narrow in purpose
- prefer explicit names over clever names
- avoid unnecessary abstractions
- write code that is easy for both humans and AI agents to read

---

## 3. Python Style

### Use type hints
All public functions, methods, and important variables should be typed where practical.

### Prefer dataclasses or Pydantic models
Use explicit models for request, response, and config data.

### Async code
- use async only where I/O requires it
- do not mix blocking calls into async request paths
- use async HTTP clients for provider calls

### Imports
- standard library first
- third-party imports next
- local imports last
- avoid circular imports

---

## 4. Naming Conventions

### Modules
- lowercase
- descriptive
- no unnecessary abbreviations

### Classes
- PascalCase

### Functions and variables
- snake_case

### Constants
- UPPER_SNAKE_CASE

### Booleans
Use clear boolean names:
- `is_enabled`
- `is_healthy`
- `has_error`
- `can_retry`

---

## 5. Architecture Discipline

- do not mix layers
- do not let UI code call provider internals directly
- do not let API routes contain routing policy
- do not let provider adapters know about UI
- do not let persistence know about HTTP
- do not let runtime know about presentation

---

## 6. Error Handling

- raise meaningful exceptions
- convert exceptions into structured API errors
- never expose secrets
- never swallow unexpected exceptions silently
- log context with request ids when possible

---

## 7. Logging Standards

- use structured logs when possible
- include request id
- include provider member id when applicable
- avoid logging API keys, full tokens, or secrets
- make logs short but useful

---

## 8. Dependency Standards

- prefer standard library first
- add third-party packages only when needed
- avoid duplicate libraries that solve the same problem
- keep V1 dependency count low

---

## 9. Testing Standards

- add tests for new behavior
- test success and failure paths
- test request translation
- test runtime decisions
- test streaming behavior
- test pool failover
- keep tests deterministic

---

## 10. Review Checklist

Before merging code, verify:
- architecture is preserved
- module responsibilities are clear
- tests pass
- no secrets are exposed
- no unnecessary dependencies are added
- UI remains consistent with the guidelines
