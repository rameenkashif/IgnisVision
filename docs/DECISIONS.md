# Decisions log

Every assumption made while building from `HANDOFF.md`. **Owner-confirmed** rows came from Rameen; **Default** rows are the handoff's fallback and can be changed — edit this file (or tell Claude) and the code follows.

## Phase 0 questions (HANDOFF §0)

| # | Topic | Status | Decision |
|---|---|---|---|
| Q1 | Repo | **Owner-confirmed** (2026-10-20) | Build in `rameenkashif/IgnisVision` as a monorepo (repo root = `ignis-vision-web/` in the handoff layout). Inputs on `main`; phase work on feature branches. |
| Q2 | Trainer media + ground truth | Default (awaiting media) | Seed 3 placeholder scenarios with generated images and hand-written ground truth, flagged `is_placeholder` / `PLACEHOLDER`. Format: HANDOFF §9.6. |
| Q3 | LLM | **Owner-confirmed**: Anthropic Claude | `LLM_PROVIDER=anthropic` support will be built behind `LLMProvider`. Default in `.env.example` stays `template` so the app runs with no key; set `LLM_PROVIDER=anthropic` + `LLM_API_KEY` in `.env` to enable. Model default `claude-sonnet-5-5` (`LLM_MODEL`). Features: report narrative, trainer feedback, help assistant — each behind a flag with template fallback. Key is never logged. |
| Q4 | Web TTS | Default | Browser `speechSynthesis`; on-screen text when no Urdu voice exists. `TTSProvider` interface ready for a cloud provider; `POST /tts` returns 501 while provider is `browser`. |
| Q5 | Brand assets | Partially received | Splash video received → `docs/reference/brand/Ignis_Vision_Splash.mp4` (will be used by the splash screen in Phase 2). Logo SVG/PNG and favicon not yet received → CSS "IV" mark as in the prototype. |
| Q6 | RPI weights | Default | `w_p=0.6, w_c=0.25, w_r=0.15`; posture P: lying 1.0, bending 0.6, sitting 0.5, standing 0.2; low-confidence factor 0.9; bands critical ≥0.75, high ≥0.55, medium ≥0.35, else low. Admin-editable. To be tuned with Rescue 1122 (SRS App. B #3). |
| Q7 | Zone fusion thresholds | Default | HANDOFF §8.2 heuristics (not analysable <15% structure; blocked ≥25% floor/door or >35% frame collapse/debris; unsafe collapse ≥0.5 conf or crack+spalling ≥5% on structural elements; caution any damage ≥0.4; stale after 120 s). Admin-editable; **must be tuned**. |
| Q8 | Deployment | **Owner-confirmed**: local Docker | Docker Compose + Caddy `tls internal`; `SITE_ADDRESS` set to the LAN IP for phone testing; mkcert alternative in README. |
| Q9 | Organisation | **Owner-confirmed**: Rescue 1122 | UI says "Rescue 1122". `stations` table seeded with one station; schema is multi-station-ready. |
| Q10 | Demo accounts | Default | `admin`, `commander1`, `responder1`, `trainee1`, `trainer1`; password printed by the seed script. |
| Q11 | Live RGB on dashboard | Default | Latest analysed frame per zone as a thumbnail, refreshed on each new result. No continuous video relay. |
| Q12 | Building layout | Default | Floors × zones grid as in the prototype; `zones.polygon` and `incidents.floor_plan_media_id` kept nullable for a later floor-plan mode. |
| Q13 | Urdu review | Default | Claude drafts Urdu strings, marked `needs_review` in `docs/i18n-review.md`. |
| Q14 | Retention | Default | No automatic deletion; retention days is an admin setting, off by default. |

## Other decisions

| Area | Decision | Why |
|---|---|---|
| RPI colours | critical + high = red, medium = yellow, low = green, always with the band label; drawn as circles/badges with the separate `--prio-*` palette so they never read as zone fills. | Reconciles SRS's four bands with its red/yellow/green wording (HANDOFF §8.1) and SRS §3.1.2's "victim colours distinct from zone colours". |
| Mobile offline sign-in | `POST /auth/mobile/login` ships the argon2 hash + params to the device, as SRS UC-08 alt flow 1 specifies. Argon2 parameters are therefore set strong (Phase 1). | Required by SRS; mitigated by parameter strength and 410 on deactivated accounts. |
| Frontend serving | `frontend` image = Caddy serving static `dist/` on :80; the separate edge `caddy` service terminates TLS and routes `/api/*`, `/ws/*` → backend, everything else → frontend. | Matches HANDOFF §2 compose layout; keeps TLS config in one place. |
| CSP | Strict CSP for the app (Google Fonts allowed). `/api/docs` gets a scoped CSP allowing jsDelivr + inline script for Swagger UI. | OpenAPI docs must stay reachable (SRS §3.3.8) without weakening the app's policy. |
| Backups | `backup` service: `pg_dump -Fc` daily into `./backups/`, deletes dumps older than `BACKUP_RETENTION_DAYS` (7), writes `backups/LAST_BACKUP` for `/admin/status`. | SRS §5.2.2. |
| Python deps | `requirements.txt` (app), `requirements-dev.txt` (tests/lint), `requirements-ml.txt` (torch etc., never installed by default). | HANDOFF §9: nothing outside `app/ml/` imports ML libs. |

## Phase 1: database, auth, RBAC

| Area | Decision | Why |
|---|---|---|
| Enums | Stored as `VARCHAR` + `CHECK` constraint (SQLAlchemy `native_enum=False`), not native PG enums. | Adding a value later is a plain migration; no `ALTER TYPE` dance. |
| Schema | Full HANDOFF §5 schema created in the first migration, so later phases add behaviour, not tables. Additions: `users.onboarding_completed`; `refresh_tokens.family_id`, `last_activity_at`, `replaced_by_id`; `incidents.deleted_at` (soft delete); `thermal_detections.client_detection_uuid`, `meta`, `model_versions`; `sync_batches.app_version`. | Needed by the onboarding flow, idle rule, rotation, audited deletes and mobile dedupe. |
| Sessions | One sign-in = one refresh-token **family**. Each refresh rotates (old row revoked, `replaced_by_id` set). Replaying a rotated token **revokes the whole family** (theft signal) — except within a 10 s grace window, which returns `409 refresh_race` so two tabs refreshing at once don't log the user out. | Rotation + reuse detection per OWASP; grace handles real multi-tab use. |
| Idle rule | Activity = login and `POST /auth/heartbeat` (stored on the session). **Refresh does not count as activity**, so a background refresh loop can't keep an idle session alive. Refresh is refused (`401 idle_timeout`) after 30 min idle unless the user is commander or current assignee of an `active` incident. The frontend sends heartbeats on user interaction and continuously on live/capture screens of an active incident. | SRS §5.3.1. |
| Logout | Authenticated by the refresh token (cookie or body), so it works after the 15-min access token expires. Ends the whole family. | Logging out must always work. |
| Deactivation | Revokes all sessions immediately. `/auth/refresh` and `/auth/mobile/refresh-bundle` return `410 account_deactivated`, checked before any other token state, so the phone always wipes its offline bundle. | SRS UC-08 AF1. |
| `must_change_password` | While set, every endpoint except `GET/PATCH /auth/me`, `/auth/change-password`, `/auth/heartbeat` and `/auth/logout` returns `403 password_change_required`. Set on admin-created users and admin resets. | SRS UC-08 AF2. |
| Argon2 params | argon2id, t=3, m=64 MiB, p=2. Hashes are transparently upgraded on login if params change. | Hash leaves the server in the mobile bundle. |
| Production guard | Backend refuses to start with `ENVIRONMENT=prod` and a placeholder `JWT_SECRET`. | Prevents shipping the example secret. |
| Admin self-protection | An admin can't deactivate or demote their own account (`409 cannot_modify_self`). | Avoids locking everyone out. |
| Confirmations | Destructive admin endpoints take `{"confirm": true}` (deactivate, reset password; later close/delete incident). | SRS §5.2.3: the API enforces it too, not only the UI dialog. |
| Seed station | "Rescue 1122 — Lahore HQ" (Lahore, Punjab). | Rescue 1122 HQ; rename via DB/admin later. |
| RBAC tests | `tests/test_rbac.py` holds the role × endpoint matrix, plus a guard test that **fails if any `/api/v1` route has no matrix row**. | Keeps §6 enforced as routers are added. |

## Phase 2: frontend shell

| Area | Decision | Why |
|---|---|---|
| Access token | Kept **in memory only** (Zustand); never in localStorage. Page reloads restore the session from the httpOnly refresh cookie via `POST /auth/refresh`. | XSS can't read a token that isn't stored. |
| Refresh | Single-flight per tab **and** across tabs (Web Locks API, `iv-refresh`), so the rotating cookie is never sent twice; `409 refresh_race` retried once as a fallback. Expired-token requests are replayed after refresh. | Avoids tripping the backend's reuse detection with multiple tabs. |
| Idle timer | Client signs out after 30 min without pointer/key/touch/wheel input, with a 60-second warning banner, unless the screen has set `keepAlive` (live/capture of an active incident, Phase 3/4) or the last heartbeat said the user is in an active incident. Heartbeat at most once a minute, only after interaction (or always under keepAlive). | Client half of SRS §5.3.1; matches the backend rule. |
| First run | `onboarding_completed = false` ⇒ sign-in → language choice → role-tailored walkthrough. Returning users get their saved profile language. The tour is replayable from Settings. | SRS §3.1.2. |
| Language | Switching sets `<html lang dir>`, saves to localStorage and the profile (`PATCH /auth/me`) and never navigates or remounts, so page state is kept. CSS uses logical properties; Urdu disables letter-spacing/uppercase (they break Arabic-script joining), uses taller line height and uses Noto Sans Arabic in place of the monospace face. | SRS §5.4.6.3. |
| Urdu fonts | Noto Nastaliq Urdu for headings, Noto Sans Arabic for body and small labels; Nastaliq is unreadable at the prototype's 9–11 px label sizes. | HANDOFF §4.1 asked to test which reads better small. |
| Navigation | `src/lib/nav.ts` mirrors HANDOFF §6. Routes are additionally wrapped in `RequireNav`, which shows "not available for your role" (the backend still returns 403 regardless). Admin sees Live/Reports/Team read-only and no trainer attempts; training staff see all trainee results. | §6 matrix. |
| Phone layout | ≤ 768 px: sidebar becomes an off-canvas drawer (mirrored in RTL), every control ≥ 48 px, no horizontal scroll at 360 px. | SRS §5.4.6.1. |
| Splash | Plays `public/splash.mp4` once per browser session (skip button, 8 s cap); skipped entirely with `prefers-reduced-motion`. | Prototype flow without annoying reloads. |
| Typed client | `backend/scripts/export_openapi.py` → `frontend/src/api/openapi.json` → `openapi-typescript` → `schema.d.ts`, used by `openapi-fetch`. A backend test and a CI step fail if either file drifts. | HANDOFF §3 (typed client from OpenAPI). |
| Not-yet-built modules | Live, Capture, Analysis, Reports, Team, Trainer, Admin render a translated "being built" placeholder with the correct title, crumbs, help topic and role guard. | Shell is complete; modules arrive in Phases 3–8. |

## Phase 3: incidents, zones, teams, live channel

| Area | Decision | Why |
|---|---|---|
| Lifecycle | The dispatch form creates the incident directly as `dispatched` (briefing state). "Teams on site — start live monitoring" → `active`. Close (with `{"confirm": true}`) → `closed`, which also ends all open team assignments (history kept) and therefore the idle-logout exemption. `draft` is kept in the schema but unused by the UI. | Mirrors the prototype's empty → briefing → live flow. |
| Incident code | `IV-<year>-<NNNN>` from a Postgres sequence (never reused, even after deletes). | Human-readable, collision-free. |
| Grid | Zone codes `F<floor>-Z<n>`, `grid_row = floor-1`, `grid_col = n-1`; the map shows the top floor first. Labels are optional and editable. | Prototype grid (Q12 default). |
| Stale rule | Applied when serving: a zone without an analysis, or whose last analysis is older than `stale_zone_seconds`, is returned as `status: "unclassified"` (with `stale: true` and the raw `stored_status`). The frontend only ever colours by `status`. Tested on both sides. | SRS §5.2.3 / §5.5.2: never show safe without a current analysis. |
| KPIs | Building status = worst current status among classified zones; evacuation % = (safe + caution) / *classified* zones, with the unclassified share shown separately; response units = distinct currently assigned responders; AI confidence = mean confidence of current (non-stale) assessments. | HANDOFF §4.2. |
| Reassignment | Assigning a responder who already has an open assignment in the incident closes the old row and opens a new one. Unassign is a soft close. | SRS UC-07 AF; full history for the report. |
| Live channels | `wss://…/ws/incidents/{id}` as specified, plus **`wss://…/ws/station`** (incident created / status change / deleted) so a second dashboard picks up a brand-new incident without polling. Both authenticate with the first message. Server pings every 25 s; the client reconnects with exponential backoff + jitter, refreshes its token on close code 4401, and refetches the aggregate after every reconnect. | HANDOFF §7.2 plus the Phase 3 exit criterion. |
| WS access | Incident channel: commanders and admins; field responders for any `active` incident or one they're assigned to (needed for zone capture in Phase 4); others `4403`. Station channel: commanders and admins. | HANDOFF §6. |
| Events | `incident.updated` carries the full aggregate (zones, KPIs, assignments), so clients just replace their cached copy. Also `assignment.changed`, `alert.created`, `alert.acknowledged`, `incident.deleted`. In-process `EventBus` with bounded per-subscriber queues (slow clients drop old events instead of blocking). | Simple and correct at SRS scale (10 users); Redis-backed bus can replace it behind the same interface. |
| Alerts | Stored as `message_key` + `params`; status words in params are translated at render time, so each viewer reads alerts in their own language. Commanders acknowledge; the newest unacknowledged critical alert turns the top bar red. | HANDOFF §5 / §4.2. |
| Delete | Admin-only soft delete (`deleted_at`) with confirmation and audit entry; deleted incidents 404 everywhere. | SRS §5.5.3. |
| Live screen keep-alive | The live view of an `active` incident sets `keepAlive`, so the client heartbeats and never idle-logs-out there. | SRS §5.3.1. |
| Zone drawer | Opens below the shell header so the language switch, Help and indicators stay reachable. | Found by the e2e test; SRS §3.1.2. |
