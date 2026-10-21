# API guide

Full, always-current reference: **`/api/docs`** (OpenAPI / Swagger UI). This page covers the cross-cutting rules and the contracts that OpenAPI can't express well. The mobile-sync contract is at the end.

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
{"type": "zone.updated", "zone_id": "…", "status": "unsafe", "analysable": true, "risk_score": 0.75, "confidence": 0.8, "assessment_id": "…", "frame_url": "/api/v1/media/…?exp=…&sig=…", "overlay_url": "…", "at": "…"}
{"type": "capture.session", "session": {"id": "…", "zone_id": "…", "zone_code": "F1-Z2", "user_id": "…", "state": "started|ended", "frames_received": 0, "frames_analysed": 0}}
{"type": "victim.upserted", "victim": { /* GET /incidents/{id}/victims item */ }}
{"type": "job.progress", "job_id": "…", "media_id": "…", "status": "running", "progress": 0.4}
```

### `/ws/station`

Allowed: incident commanders and admins. Keeps incident lists current.

```jsonc
{"type": "incident.created", "incident": { /* IncidentSummary */ }}
{"type": "incident.updated", "incident": { /* IncidentSummary */ }}
{"type": "incident.deleted", "incident_id": "…"}
```

### `/ws/capture` (zone capture from a phone)

Allowed: incident commanders and field responders, for any zone of an `active` incident (`GET /capture/targets` lists them, own assignments first).

1. `{"type": "auth", "token": "…"}`, then `{"type": "start", "zone_id": "…"}`.
   Reply: `{"type": "started", "session_id": "…", "target_fps": 1.0, "zone_code": "F1-Z2"}`.
2. Send **binary JPEG frames** (≤ 2 MB, ~960 px wide) at `target_fps`. The server keeps only the newest frame (latest-frame-wins) and answers each analysed frame with:

   ```json
   {"type": "zone_result", "zone_id": "…", "zone_code": "F1-Z2", "status": "caution", "analysable": true,
    "risk_score": 0.4, "confidence": 0.81,
    "reasons": [{"key": "reasons.damage_present", "params": {"cls": "crack", "conf": 48}}],
    "damage": [{"cls": "crack", "confidence": 0.48, "area_pct": 1.5, "element": "wall", "polygon": [[0.1, 0.3], …]}],
    "frame_url": "/api/v1/media/…?exp=…&sig=…", "overlay_url": "…", "latency_ms": 62}
   ```

   When analysis isn't possible (`analysable: false`), `status` is the zone's previous status, never "safe" by default.
3. Alerts for this zone: `{"type": "alert", "severity": "crit", "alert_type": "zone_rapid_change", "message_key": "alerts.zone_rapid_change", "params": {"zone": "F1-Z2", "from": "caution", "to": "unsafe"}}`. Speak them with the `voice.<alert_type>` template.
4. Bad frames: `{"type": "error", "code": "not_jpeg" | "frame_too_large" | "undecodable_frame"}` (the session continues).
5. `{"type": "stop"}` ends the session cleanly. A dropped connection ends it too and raises a `camera_lost` info alert.

Close codes: `4401` auth, `4403` zone not capturable (role, inactive incident), `4400` malformed start.

## Thermal uploads

- `POST /incidents/{id}/thermal-uploads` (multipart: `file`, optional `zone_id`) → `202 {media_id, job_id}`. JPEG/PNG ≤ 20 MB, MP4/WebM/MOV ≤ 300 MB.
- `GET /jobs/{job_id}` → `{status: queued|running|done|failed, progress, model_name, model_version, error}`.
- `GET /media/{media_id}/detections` → per-detection `bbox` (normalised xyxy), `keypoints`, `posture`, `low_confidence`, `rpi_score`, `rpi_band`, `frame_index`, `timestamp_ms`, `frame_url`.
- `GET /media/{media_id}/frames` → the 2 fps samples a video was analysed on (signed `url` each).
- `GET /incidents/{id}/victims` → ranked people (RPI desc; rescued / not-a-person last). `PATCH /victims/{id}` `{status: detected|rescued|false_positive}` (commander).
- `GET /incidents/{id}/thermal-uploads` → upload history with job state, counts and signed URLs (commander/admin).

## Mobile sync — `POST /api/v1/sync/incidents`

For the Flutter app (roles: field responder, incident commander). **Idempotent**: post the same payload any number of times; each incident is created once.

```jsonc
{
  "device_id": "android-7f3c…",
  "app_version": "1.0.0",
  "incidents": [{
    "client_uuid": "c0b4e1a2-…",            // dedupe key, generated on the phone
    "started_at": "2026-10-20T09:55:00Z",
    "ended_at": "2026-10-20T10:20:00Z",      // omit while still ongoing → incident stays active
    "label": "Anarkali basement",
    "linked_incident_id": null,              // or a web incident id to attach the detections to it
    "detections": [{
      "client_detection_uuid": "c0b4e1a2-…-0001",
      "captured_at": "2026-10-20T10:00:00Z",
      "mode": "live",                        // live | still
      "track_id": 3,                         // same id = same person
      "bbox": [0.2, 0.3, 0.4, 0.9],          // normalised x1,y1,x2,y2
      "keypoints": [[0.31, 0.35, 0.92], …],  // optional, 17 × [x, y, conf]
      "posture": "lying",                    // standing | sitting | lying | bending
      "posture_confidence": 0.81,
      "low_confidence": false,
      "detection_confidence": 0.88,
      "env_risk": 0.0,                       // optional 0–1
      "rpi_score": 0.86, "rpi_band": "critical",   // phone's values, kept for comparison
      "frame_ref": "frame_0012.jpg"          // optional: name of a multipart file part
    }]
  }]
}
```

- Content type `application/json`, **or** `multipart/form-data` with a `payload` part (the JSON above) plus image parts whose **filename** equals `frame_ref`.
- Response `200`:

  ```json
  {"results": [{"client_uuid": "c0b4e1a2-…", "status": "created", "incident_id": "…", "error": null}]}
  ```

  `status` is `created`, `duplicate` (already received; mark as sent) or `error` (e.g. `incident_not_found` for a bad `linked_incident_id`; other items still succeed).
- The server **recomputes RPI** with its current settings; the phone's values are stored in the detection's `meta` (`mobile_rpi`, `mobile_band`).
