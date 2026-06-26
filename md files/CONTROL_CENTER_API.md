# AEGIS Control Center API

## 1. Purpose

This document defines the backend API surface used by the AEGIS Control Center UI.

These endpoints are for administrative and operational use, not for Claude Code request traffic.

---

## 2. Access Control

All Control Center endpoints should require AEGIS authentication.

### Rules
- no anonymous admin access
- no public write endpoints
- no secrets returned in responses
- use the same auth token system or a dedicated admin token if needed

---

## 3. Dashboard Endpoints

### `GET /api/dashboard/summary`
Returns high-level server health and pool metrics.

#### Example response
```json
{
  "server": {
    "status": "running",
    "version": "v1"
  },
  "pool": {
    "total_members": 2,
    "healthy_members": 2,
    "disabled_members": 0,
    "active_members": 1
  },
  "runtime": {
    "scheduler": "health-first",
    "streaming": true
  }
}
```

---

## 4. Provider Pool Endpoints

### `GET /api/providers`
Returns all configured NVIDIA pool members.

### `POST /api/providers`
Adds a new provider member.

### `PUT /api/providers/{provider_id}`
Updates a provider member.

### `DELETE /api/providers/{provider_id}`
Removes a provider member.

### `POST /api/providers/{provider_id}/enable`
Enables a provider member.

### `POST /api/providers/{provider_id}/disable`
Disables a provider member.

### `POST /api/providers/{provider_id}/test`
Runs a connectivity test against the provider member.

---

## 5. Runtime Endpoints

### `GET /api/runtime`
Returns runtime settings.

### `PUT /api/runtime`
Updates runtime settings.

### Suggested runtime fields
- scheduler mode
- retry count
- timeout
- cooldown duration
- streaming enabled
- thinking enabled
- request size limit

---

## 6. Logs Endpoints

### `GET /api/logs`
Returns recent request and error logs.

### Query parameters
- `limit`
- `offset`
- `severity`
- `request_id`
- `provider_id`

### `GET /api/logs/{request_id}`
Returns detailed information for a single request.

---

## 7. Health Endpoints for Control Center

### `GET /api/control/health`
Returns backend health data used by the UI.

This can reuse the same internal data source as `/status`, but the payload may be richer for dashboard rendering.

---

## 8. Settings Endpoints

### `GET /api/settings`
Returns non-secret settings relevant to the Control Center.

### `PUT /api/settings`
Updates safe runtime and UI-related settings.

### Rules
- do not return secrets
- do not allow arbitrary writes
- validate every field

---

## 9. Response Rules

All Control Center responses should:
- be structured JSON
- be consistent
- avoid leaking provider secrets
- include useful status metadata
- support the UI without extra transformation

---

## 10. UI Integration Rules

The Control Center should be able to:
- read current pool health
- update provider state
- update runtime settings
- show recent logs
- test provider connectivity
- render clear success/error states
