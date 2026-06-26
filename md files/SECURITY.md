# AEGIS Security Guidelines

## 1. Purpose

This document defines the security principles for AEGIS.

AEGIS handles API keys, gateway access, request payloads, and internal provider routing, so security must be part of the design from the beginning.

---

## 2. Core Security Principles

- protect secrets
- validate inputs
- fail safely
- log carefully
- minimize attack surface
- keep auth strict
- keep configuration explicit

---

## 3. Secret Handling

### Rules
- never commit API keys
- never print API keys in logs
- never expose raw secrets in the UI
- store secrets securely
- mask sensitive values in diagnostics

### Storage note
If secrets must be stored locally for V1, they should be protected as much as possible and never returned to the browser unmasked.

---

## 4. Authentication

### Rules
- all protected endpoints must require authentication
- missing or invalid auth must fail early
- do not allow anonymous access to control endpoints
- separate gateway auth from provider credentials

---

## 5. Input Validation

### Rules
- validate all incoming JSON
- reject malformed payloads quickly
- do not trust client-provided fields blindly
- validate message structure, stream flags, and tool payloads
- sanitize strings used in logs or UI

---

## 6. Provider Security

### Rules
- keep provider credentials isolated from request payloads
- never expose provider keys to clients
- keep provider adapter code narrow
- do not mix provider state with public metadata

---

## 7. Logging Security

### Do not log
- raw API keys
- bearer tokens
- full authorization headers
- private request payloads if they contain secrets
- encrypted secret values if they are not needed for debugging

### Do log
- request ids
- status codes
- safe provider labels
- timing information
- error categories

---

## 8. Rate Limiting and Abuse Control

AEGIS should be designed so that future rate limiting can be added easily.

### Initial expectations
- avoid retry storms
- enforce bounded retries
- respect provider cooldowns
- support request backoff logic
- avoid flooding a failing provider

---

## 9. UI Security

- do not display secrets in the Control Center
- mask sensitive values
- confirm destructive actions
- keep admin actions authenticated

---

## 10. Transport Security

- assume HTTPS in production
- avoid sending secrets over insecure channels
- do not expose admin endpoints without protection

---

## 11. Safe Failure Behavior

When something goes wrong:
- fail with a clear structured error
- do not leak internal stack traces to clients
- keep logs detailed enough for operators
- keep user-facing errors short and safe

---

## 12. Security Review Checklist

Before release, verify:
- no secrets are visible in logs
- auth works on every protected route
- invalid payloads are rejected
- provider errors do not leak secrets
- UI does not expose sensitive data
- retry logic is bounded
