# API guide

Full, always-current reference: **`/api/docs`** (OpenAPI / Swagger UI). This page covers the cross-cutting rules and the contracts that OpenAPI can't express well. The mobile-sync contract is added in Phase 5.

## Conventions

- Base path `/api/v1`. JSON everywhere. Every endpoint except `/health*`, `/auth/login` and `/auth/mobile/login` needs authentication.
- **Errors** always use one envelope, so the frontend can translate them:

  ```json
  { "error": { "code": "invalid_credentials", "message_key": "errors.invalid_credentials", "params": {} } }
  ```

  Validation failures are `422` with `code: "validation_failed"` and `params.fields`.
- Lists return `{ "items": [...], "total": n }` and accept `limit` / `offset`.
- Destructive actions require `{"confirm": true}` in the body.

## Authentication (web)

1. `POST /auth/login` `{username, password}` → `{access_token, expires_in: 900, idle_timeout_s: 1800, user}` and an **httpOnly, Secure, SameSite=Strict** cookie `iv_refresh` scoped to `/api/v1/auth`.
2. Send `Authorization: Bearer <access_token>` on every call (and as the first WebSocket message, later).
3. When the access token expires (`401 token_expired`), call `POST /auth/refresh` (no body; the cookie is sent automatically). You get a new access token and a rotated cookie.
   - `409 refresh_race`: another tab refreshed at the same moment. Retry once.
   - `401 idle_timeout` / `session_expired` / `refresh_reused` / `invalid_token`: go to sign-in.
   - `410 account_deactivated`: go to sign-in and show the deactivated message.
4. `POST /auth/heartbeat` on user interaction (throttled, e.g. once a minute) and every minute while on the live dashboard or capture screen of an active incident. A session with no activity for 30 minutes cannot refresh, unless the user is in an active incident.
5. `POST /auth/logout` ends the session (works even after the access token expired).
6. If `user.must_change_password` is true, only `/auth/me`, `/auth/change-password`, `/auth/heartbeat` and `/auth/logout` work until `POST /auth/change-password` `{current_password, new_password}` succeeds.

Password rule (SRS §5.5.4): at least 8 characters, containing letters and numbers.

## Authentication (mobile app)

- `POST /auth/mobile/login` `{username, password, device_id?}` → tokens in the **body** (`access_token`, `refresh_token`, `refresh_expires_at`) plus `credential_bundle`:

  ```json
  { "user_id": "…", "username": "responder1", "full_name": "…", "role": "field_responder",
    "preferred_language": "ur", "password_hash": "$argon2id$v=19$m=65536,t=3,p=2$…",
    "hash_params": { "algorithm": "argon2id", "version": 19, "time_cost": 3, "memory_cost": 65536,
                     "parallelism": 2, "hash_len": 32, "salt_len": 16 },
    "issued_at": "…" }
  ```

  Store it in secure storage; verify the password offline against `password_hash` with argon2id.
- `POST /auth/refresh` with body `{"refresh_token": "…"}` → new access **and** refresh token in the body.
- `GET /auth/mobile/refresh-bundle` (Bearer) → a fresh bundle, or **`410 Gone`** if the account was deactivated: wipe the stored bundle.

## Roles

`admin`, `incident_commander`, `field_responder`, `trainee`, `training_staff`. The access matrix is HANDOFF §6 and is enforced and tested in `backend/tests/test_rbac.py`.

## Live channels (WebSocket)

Both use `wss://<host>/ws/...` and the same handshake:

1. Connect, then send `{"type": "auth", "token": "<access token>"}` as the **first** message (never put the token in the URL).
2. The server replies `{"type": "ready", ...}` and then streams events. It sends `{"type": "ping"}` every 25 s; you may send `{"type": "ping"}` and get `{"type": "pong"}`.
3. Close codes: `4401` (missing/expired/invalid token: refresh and reconnect), `4403` (role not allowed), `4404` (incident not found). Before closing, the server sends `{"type": "error", "code": "..."}`.
4. After every (re)connect, refetch `GET /incidents/{id}`; events are not replayed.

### `/ws/incidents/{incident_id}`

Allowed: incident commanders, admins; field responders for an `active` incident or one they are assigned to.

```jsonc
{"type": "incident.updated", "incident": { /* full GET /incidents/{id} body: zones, kpis, assignments */ }}
{"type": "assignment.changed", "assignment": {"id": "…", "zone_code": "F1-Z2", "user": {…}, "unassigned_at": null, …}}
{"type": "alert.created", "alert": {"id": "…", "severity": "crit", "type": "zone_unsafe", "message_key": "alerts.zone_unsafe", "message_params": {"zone": "F1-Z2"}, …}}
{"type": "alert.acknowledged", "alert": {…}}
{"type": "incident.deleted", "incident_id": "…"}
// From Phase 4/5: zone.updated, victim.upserted, job.progress, capture.session
```

### `/ws/station`

Allowed: incident commanders and admins. Keeps incident lists current.

```jsonc
{"type": "incident.created", "incident": { /* IncidentSummary */ }}
{"type": "incident.updated", "incident": { /* IncidentSummary */ }}
{"type": "incident.deleted", "incident_id": "…"}
```
