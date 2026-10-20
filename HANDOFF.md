# Ignis Vision Web App: Claude Code Handoff

> **For Claude Code.** This file is your brief for building the **Ignis Vision web application**: the React frontend, the FastAPI backend, the PostgreSQL database and the Docker setup, all running from start to finish. When you finish, **the only work left should be plugging in the trained ML models.** Every model call goes through an interface you build, and a working mock sits behind it, so the whole app can be demoed before any real weights exist.
>
> Source documents. Put both in `docs/reference/` before starting:
> - `docs/reference/ignis_vision_dashboard.html` is the **visual and UX reference** (the prototype "Commander Dashboard").
> - `docs/reference/Ignis-Vision-SRS-2.0.docx` is the **requirements authority** (IEEE SRS v2.0, 8 Oct 2026). You can read it with `pandoc -t plain`.
>
> **Precedence rule:** if the HTML prototype and the SRS disagree, **the SRS wins** for behaviour and scope, and **the HTML wins** for look and feel. Known conflicts are listed in §4.

---

## 0. Start here: ask the owner before you build

Before you write any code, **ask the project owner (Rameen) all of the questions below in one batch.** Don't stall waiting for answers. For anything left unanswered, go ahead with the stated default and record it in `docs/DECISIONS.md`, so the owner can see what you assumed and change it later.

| # | Question to ask | Why it matters | Default if unanswered |
|---|---|---|---|
| Q1 | **Repo:** should this be built in the existing `rameenkashif/ignisVision_demo` repo, or in a new monorepo? | Decides where code and CI live. | Use the current working directory as a new monorepo. |
| Q2 | **Simulation trainer media:** please send the training scenario images and videos, plus the correct answer for each one (zone status per zone region, posture per visible person). The format is in §9.6. How many scenarios are there? Are they real incident footage (permission from Rescue 1122?) or simulated? | The trainer can't be graded without ground truth. | Seed 3 placeholder scenarios with generated placeholder images and hand-written ground truth, clearly marked `PLACEHOLDER`. |
| Q3 | **LLM API:** which provider (Anthropic Claude / OpenAI / Google Gemini / Groq / other) and which model? Send the API key through a `.env` file, **never in chat**. Which LLM features do you want: report narrative, trainer feedback, in-app help assistant? (See §10.) | Optional features depend on it. | No LLM. Every LLM feature falls back to deterministic templates, and the app stays fully functional. |
| Q4 | **Web text-to-speech:** use the browser's built-in `speechSynthesis` (free, but Urdu voice support varies by browser and OS), or a cloud TTS (which provider and key)? The SRS leaves this TBD (Appendix B). | Urdu spoken alerts on the web. | Browser TTS, falling back to on-screen text when no Urdu voice is available. A `TTSProvider` interface is ready for a cloud provider. |
| Q5 | **Brand assets:** the prototype references `Ignis_Vision_Splash.mp4` and an "IV" mark. Can you send the splash video, logo SVG/PNG and favicon? | Splash and branding. | CSS-only animated splash and a text "IV" mark, as in the prototype. |
| Q6 | **RPI weights:** what values should `w_p`, `w_c`, `w_r`, the posture severity scores and the priority band thresholds take? (SRS Appendix B #3 says these will be tuned with Rescue 1122.) | Victim ranking. | The defaults in §8.1, editable by an admin in Settings. |
| Q7 | **Zone risk fusion thresholds:** what damage area or percentage should make a zone *caution*, *unsafe* or *blocked*? | Zone classification. | The heuristic defaults in §8.2, editable by an admin. |
| Q8 | **Deployment target:** local Docker only for now, or a server or VPS with a domain? The phone camera needs HTTPS. | TLS and hosting setup. | Docker Compose with Caddy serving local HTTPS (`tls internal`), plus `mkcert` instructions for testing on a phone over LAN. |
| Q9 | **Organisation name in the UI:** the prototype says "Karachi Fire Department"; the SRS says Rescue 1122 (Punjab Emergency Service). Which should appear, and should the app support multiple stations? | Branding and data model. | "Rescue 1122". A `stations` table exists (SRS §5.1.3), seeded with one station. |
| Q10 | **Seed and demo accounts:** which names should the demo users have, one per role? | Demo login. | Generic users (`admin`, `commander1`, `responder1`, `trainee1`, `trainer1`) with the password printed by the seed script. |
| Q11 | **Live RGB zone video on the commander dashboard:** continuous video, periodic snapshots, or none? The SRS leaves this TBD (Appendix B #8). | Bandwidth and UI. | Latest analysed frame per zone as a thumbnail, refreshed whenever a new result arrives. No continuous video relay. |
| Q12 | **Building layout:** keep the prototype's floors × zones **grid**, or should commanders upload a floor-plan image and draw zones on it? | Zone map UI. | Grid, as in the prototype. Schema keeps an optional `floor_plan_media_id` for later. |
| Q13 | **Urdu translations:** who will review the Urdu strings? | Bilingual quality. | You draft the Urdu strings and mark them `needs_review` in `docs/i18n-review.md`. |
| Q14 | **Data retention:** how many days should incidents and footage be kept? (SRS §5.5.3 defers to Rescue 1122 policy.) | Cleanup jobs. | No automatic deletion. Retention is an admin setting and is off by default. |

Ask anything else you need along the way, but keep it batched and always continue with a sensible default.

---

## 1. What Ignis Vision is (context in 60 seconds)

Ignis Vision is an AI fire-incident response system for **Rescue 1122**, built as a NUST MCS final-year project (supervisor: Dr Ayesha Naseer). It has two applications:

- **Mobile app (Flutter, offline). NOT in this handoff.** It is the field responder's tool, and the only app connected to the USB-C thermal camera. It detects people in smoke, classifies their posture, computes a Rescue Priority Index (RPI) and gives spoken Urdu/English alerts, all with no internet. Later, when internet is available, it **uploads** saved incident data to the web backend.
- **Web app. THIS handoff.** It is used when internet is available: at the command post (desktop or laptop), and on mobile browsers by responders capturing zones. It provides:
  1. **Building structure and zone risk analysis** from **live RGB video captured with a phone's camera** in the browser. SegFormer-B2 handles building elements and YOLO-seg handles structural damage. Each zone is classified as **safe / caution / unsafe / blocked**, and a zone with no current analysis is **unclassified**.
  2. **Analysis of uploaded thermal images and videos.** A YOLO-pose model runs on the server for person detection plus posture (standing / sitting / lying / bending), followed by RPI.
  3. An **Incident Command Dashboard**: log incidents, define zones, assign teams, view the live zone risk map, alerts and the ranked victim list.
  4. A **Simulation Trainer**: trainees classify zones and postures in real incident media and are compared against the reference answers.
  5. **Incident records and reports**, with PDF export.
  6. **Authentication, roles and administration.**
  7. **English and Urdu throughout**, with Urdu laid out right to left.

**The web app never shows live thermal video.** Thermal data reaches it only through uploads, either a user uploading a file on the web or the mobile app syncing its data.

---

## 2. Tech stack (fixed by SRS §3.3, details are your call within these)

| Layer | Choice |
|---|---|
| Frontend | **React 18 + TypeScript + Vite**, React Router, TanStack Query (server state), Zustand (UI and live state), **react-i18next** (EN/UR plus RTL), plain CSS modules or CSS variables ported from the prototype (no heavy UI kit; the look must match the prototype). |
| Backend | **FastAPI on Python 3.11**, Pydantic v2, **SQLAlchemy 2.0 (async) + asyncpg**, **Alembic** migrations, native FastAPI WebSockets, `argon2-cffi` for password hashing, PyJWT for tokens, WeasyPrint (or ReportLab) for PDF reports, OpenCV and Pillow for frame and video handling. |
| Database | **PostgreSQL 16**. |
| Background work | An in-process asyncio job queue backed by a `analysis_jobs` table (enough for SRS load: 10 users, 5 live captures). Keep it behind a `JobQueue` interface so it can be swapped for Redis/RQ/Celery later without touching callers (SRS §5.1.3). |
| Pub/sub for live events | An in-process `EventBus` interface (asyncio fan-out to WebSocket subscribers), with a Redis implementation optional later. |
| File storage | A `StorageBackend` interface with a local-disk implementation (`/data/media`), S3-compatible later. |
| Packaging | **Docker Compose**: `db`, `backend`, `frontend` (built and served by Caddy), `caddy` (HTTPS reverse proxy for `/api`, `/ws` and static files), `backup` (daily `pg_dump`, SRS §5.2.2). |
| Tests | pytest + httpx (backend, with a real Postgres test DB via compose), Vitest + Testing Library (frontend units), **Playwright** (end-to-end smoke). Chromium is available for Playwright. |

Coding standards: PEP 8 with `ruff` and `black`; ESLint and Prettier for TS; conventional commits (SRS §2.5.7).

---

## 3. Repository layout

```
ignis-vision-web/
├── HANDOFF.md                     ← this file
├── docker-compose.yml
├── docker-compose.dev.yml         ← hot reload, exposed ports
├── Caddyfile
├── .env.example                   ← every env var, documented; real .env is git-ignored
├── docs/
│   ├── reference/                 ← prototype HTML + SRS (inputs)
│   ├── DECISIONS.md               ← every default you assumed (§0) + why
│   ├── MODEL_INTEGRATION.md       ← YOU write this: exact steps to plug real models (§11)
│   ├── API.md                     ← short guide; full spec is FastAPI /docs (OpenAPI)
│   └── i18n-review.md
├── backend/
│   ├── pyproject.toml
│   ├── requirements.txt           ← app deps
│   ├── requirements-ml.txt        ← torch/ultralytics/transformers — NOT installed by default
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                  ← config (pydantic-settings), security, logging, deps
│   │   ├── db/                    ← engine, session, base, seed.py
│   │   ├── models/                ← SQLAlchemy models
│   │   ├── schemas/               ← Pydantic DTOs
│   │   ├── api/v1/                ← routers: auth, users, incidents, zones, teams, capture,
│   │   │                             uploads, detections, alerts, reports, training,
│   │   │                             sync (mobile), settings, admin, tts, help, health
│   │   ├── ws/                    ← websocket endpoints + connection manager
│   │   ├── services/              ← business logic (rpi.py, zone_fusion.py, alerts.py,
│   │   │                             reports.py, training_grader.py, tracking.py, audit.py)
│   │   ├── ml/                    ← MODEL SEAM — see §9
│   │   │   ├── contracts.py       ← Protocols + dataclasses (the contract)
│   │   │   ├── registry.py        ← picks mock vs real via env
│   │   │   ├── mock/              ← deterministic mocks (default)
│   │   │   └── real/              ← stubs raising NotImplementedError + TODOs
│   │   ├── llm/                   ← LLMProvider interface + providers + template fallback
│   │   ├── tts/                   ← TTSProvider interface (browser = no-op server side)
│   │   ├── storage/
│   │   ├── jobs/                  ← JobQueue + workers (video/image analysis)
│   │   └── events/                ← EventBus
│   └── tests/
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── public/                    ← fonts fallback, splash asset (if provided)
    └── src/
        ├── main.tsx, App.tsx, routes.tsx
        ├── styles/tokens.css      ← ported :root variables from prototype
        ├── i18n/{en,ur}.json
        ├── api/                   ← typed client (generate from OpenAPI with openapi-typescript)
        ├── ws/                    ← reconnecting WS client + hooks
        ├── stores/
        ├── components/            ← Sidebar, Topbar, KpiStrip, Panel, ZoneGrid, ZoneCell,
        │                             AlertFeed, VictimList, Donut, EvacBar, StatusChip,
        │                             LangSwitch, HelpButton, ConnIndicator, CamIndicator,
        │                             ConfirmDialog, Modal, FileDrop, MediaViewer(+overlay)
        ├── features/              ← onboarding, auth, live, capture, analysis, reports,
        │                             incident-setup, team, trainer, admin, settings, help
        └── lib/                   ← tts.ts, idle-timer.ts, format.ts, colors.ts
```

---

## 4. Reading the prototype: what to keep, change and add

The prototype (`ignis_vision_dashboard.html`) is a single-file vanilla-JS demo with simulated data. **Reproduce its visual language faithfully in React**: dark theme, the colour tokens, the three fonts, panel/KPI/zone-cell styling, the sidebar with collapse, the dispatch modal, and the alerts that jump to a feed.

### 4.1 Design tokens to port verbatim (`styles/tokens.css`)
```css
--bg-0:#0A0D10; --bg-1:#10151A; --bg-2:#161C22; --bg-3:#1D242B;
--line:#262E36; --line-soft:#1B2128;
--text-hi:#EDEFF1; --text-mid:#9AA4AC; --text-low:#5B646C;
--safe:#2FA66E; --safe-dim:#173D2C;
--caution:#E8A93B; --caution-dim:#4A3813;
--unsafe:#DD4A32; --unsafe-dim:#4A1D14;
--blocked:#6B2E33; --blocked-dim:#2A1416;
--thermal:#FF6A2B; --accent:#3FA9E8;
--font-display:'Space Grotesk'; --font-mono:'IBM Plex Mono'; --font-body:'Inter';
--sidebar-w:224px; --sidebar-w-collapsed:64px;
```
Add `--unclassified` (a neutral grey with a hatched pattern) and Urdu font tokens (`Noto Nastaliq Urdu` for display, `Noto Sans Arabic` for body; test which reads better at small sizes).

**Victim priority colours must be separate from the zone colours** (SRS §3.1.2). Use a separate set such as `--prio-critical`, `--prio-high`, `--prio-medium`, `--prio-low`, and draw victim markers as circles or badges while zones are filled cells. **Every colour always has a text label** for colour-blind users.

### 4.2 Screen mapping

| Prototype element | Keep / change | Notes |
|---|---|---|
| Splash, then Sign-in, then Language | **Keep** the flow | Real auth. The language choice is saved to the user profile and to localStorage. Show the onboarding walkthrough on first use; it can be reopened from Settings (SRS §3.1.2). |
| Sidebar: Live monitoring, Camera demo, Incident reports, Image analysis, Team deployment, Training simulator, Settings | **Keep the structure, change the items** | Items are filtered by role (§6). "Camera demo" becomes **Zone Capture** (real). "Image analysis" becomes **Thermal & Image Analysis** (real uploads). Add **Admin** and **Help**. |
| Live monitoring: empty state, then briefing (teams dispatched), then live state | **Keep** all three states | They are driven by the incident status (`draft` → `dispatched` → `active` → `closed`). |
| KPI strip (Active incident, Victims, Building status, Response units, AI confidence) | **Keep** | Built from real data. "Victims" counts uploaded or analysed thermal detections. |
| **Thermal camera live panel** | **CHANGE** | The SRS forbids live thermal on the web. Replace it with a **"Thermal detections" panel**: the latest analysed thermal image or video frame with boxes and posture labels, plus the source (web upload or mobile sync) and a timestamp. |
| RGB camera panel per cam tab | **Change** | Show the **latest analysed RGB frame per zone** from capture sessions, with a segmentation and damage overlay toggle. The tabs become **capture sessions / zones**, not "Cam 1–3" (see Q11). |
| Structural map (zone grid) | **Keep and extend** | Five states: safe, caution, unsafe, **blocked** (missing from the prototype legend), and **unclassified** (with stale data shown as unclassified, never safe). Victim marker on a zone if it has detections. Show the assignee on each cell. Clicking a zone opens a drawer with its history. |
| Real-time alerts, clickable to jump to a feed | **Keep** | Driven by the backend through the WebSocket. Severity levels `crit` / `warn` / `info`. Critical alerts also turn the top bar red and are spoken aloud. |
| Humans detected list | **Keep** and rank it **by RPI** | Each row shows rank, RPI band chip with label, posture with a low-confidence flag, confidence, zone and source. |
| Zone classification donut | **Keep** | Add blocked and unclassified segments. |
| Building safety threshold (evacuation bar, 40%) | **Keep** | The threshold is an admin setting. Count only *currently classified* zones; show the unclassified share separately. |
| Dispatch modal: location, structure type, incident type, reported by; floors × zones; team rows (firefighter, zone, camera rig) | **Keep** | Persist it. Team rows pick **real users** with the `field_responder` role. "Camera rig" becomes an optional free-text device label. A team can be reassigned during an incident (SRS UC-07 alternative flow). |
| Camera demo (TF.js COCO-SSD, simulated thermal) | **Replace** with Zone Capture | Remove TF.js and in-browser models. The phone camera streams frames to the backend over WSS (§7.3). Keep the excellent "camera blocked on `file://`/HTTP" troubleshooting messages, adapted for HTTPS. |
| Incident reports table plus "Export PDF" | **Keep** | Real list with filters. Detail page includes the timeline, zone history, victims, media and a PDF. |
| Training simulator placeholder | **Build fully** | §9.6. |
| Settings (sound alerts, evacuation threshold) | **Keep and extend** | Split into per-user preferences and admin-only system settings. |
| Hard-coded "Rimsha Irfan / Incident Commander" | **Change** | Use the logged-in user. |

### 4.3 Missing from the prototype (required by the SRS)
- **Admin panel** (users, roles, deactivate, reset password, training scenarios, system status, audit log), SRS §4.8.
- **Field Responder mobile-browser view**: a simplified capture screen with big buttons, spoken zone alerts and a zone map (SRS §2.3.1, §3.1.1).
- **Trainee and Training Staff views** (§9.6).
- **Help** button on every screen, linking to in-app help pages (SRS §2.6.3).
- **Language switch, internet connection indicator, and camera indicator** (on screens that use the camera) on **every screen after sign-in** (SRS §3.1.2).
- **Urdu RTL** everywhere, with switching that loses no state (SRS §5.4.6.3).
- **Responsive design from 360px**, with **48px minimum touch targets** on mobile (SRS §5.4.6.1).
- **Confirmation dialogs** for closing an incident, deleting records and deactivating accounts (SRS §5.2.3).
- **Short, actionable error messages** in the selected language. On mobile-browser screens, important errors are also spoken (SRS §3.1.2).

---

## 5. Database schema (PostgreSQL)

Use UUID primary keys (`uuid7` or `gen_random_uuid()`), `created_at` and `updated_at` timestamps with timezone, and soft deletes where the SRS wants traceability. Every table gets an Alembic migration. Below are suggested columns; add indexes for the obvious foreign keys and filters.

**Identity and administration**
- `stations`: id, name, city, region. Seeded with one station.
- `users`: id, station_id, username (unique, case-insensitive), full_name, password_hash (argon2), role (enum below), preferred_language (`en|ur`), is_active, must_change_password, last_login_at.
  - `role` enum: `admin`, `incident_commander`, `field_responder`, `trainee`, `training_staff`.
- `refresh_tokens`: id, user_id, token_hash, issued_at, expires_at, last_used_at, revoked_at, user_agent, device_kind (`web|mobile`).
- `audit_logs`: id, actor_user_id, action, entity_type, entity_id, before (jsonb), after (jsonb), ip, created_at. This records **all admin changes and every deletion** (SRS §4.8 REQ-6, §5.5.3).
- `system_settings`: key (pk), value (jsonb), updated_by, updated_at. It holds the RPI weights, posture severities, priority bands, zone fusion thresholds, stale-zone timeout, evacuation threshold, capture fps, retention days, and the alert rapid-change window.

**Incidents**
- `incidents`: id, station_id, code (human-readable, e.g. `IV-2026-0412`, via a sequence), address, city, structure_type (`commercial|residential|industrial|other`), incident_type (`structural|chemical|electrical|other`), reported_by, status (`draft|dispatched|active|closed`), commander_id, opened_at, activated_at, closed_at, closed_by, summary_text (nullable), floor_plan_media_id (nullable), **source** (`web|mobile_sync`), **client_uuid** (nullable, unique; used to deduplicate mobile uploads).
- `floors`: id, incident_id, number, label.
- `zones`: id, incident_id, floor_id, code (e.g. `F1-Z3`), label, grid_row, grid_col, polygon (jsonb, nullable for the future floor-plan mode), **current_status** (`unclassified|safe|caution|unsafe|blocked`), current_assessment_id, status_updated_at.
- `team_assignments`: id, incident_id, zone_id, user_id, device_label, assigned_at, unassigned_at, assigned_by. Keep the history rather than overwriting.

**Capture and analysis**
- `capture_sessions`: id, incident_id, zone_id, user_id, started_at, ended_at, frames_received, frames_analysed, recording_media_id (nullable). Store sampled analysed frames and, optionally, a stitched recording (SRS: "footage is recorded on the server").
- `media_assets`: id, incident_id (nullable for training media), kind (`thermal_image|thermal_video|rgb_frame|rgb_recording|training_image|training_video|report_pdf|floor_plan`), storage_key, mime, bytes, width, height, duration_s, sha256, uploaded_by, source (`web_upload|capture|mobile_sync|seed`).
- `analysis_jobs`: id, media_id, job_type (`thermal_pose|zone_structure`), status (`queued|running|done|failed`), progress, error, model_name, model_version, started_at, finished_at.
- `zone_assessments`: id, zone_id, capture_session_id, media_id (frame), status, risk_score (0–1), confidence, analysable (bool), reasons (jsonb, e.g. `["crack area 7.2% on wall"]`), segmentation_summary (jsonb: class → pixel %), damage_instances (jsonb), model_versions (jsonb), created_at. **Insert only**; this is the zone risk history (SRS UC-05 postcondition).
- `thermal_detections`: id, incident_id, zone_id (nullable), media_id, analysis_job_id (nullable), frame_index / timestamp_ms, track_id, bbox (jsonb, normalised xyxy), keypoints (jsonb, 17×[x,y,conf]), posture (`standing|sitting|lying|bending`), posture_confidence, low_confidence (bool), detection_confidence, env_risk (0–1, default 0), **rpi_score**, **rpi_band** (`critical|high|medium|low`), source (`web_upload|mobile_sync`), detected_at.
- `victims`: id, incident_id, zone_id, track_key, best_detection_id, latest_posture, latest_rpi_score, latest_rpi_band, first_seen_at, last_seen_at, status (`detected|rescued|false_positive`), source. These are aggregated per tracked person, which gives the dashboard a stable ranked list.
- `alerts`: id, incident_id, zone_id (nullable), severity (`crit|warn|info`), type (`zone_rapid_change|zone_unsafe|zone_blocked|victim_critical|analysis_failed|camera_lost|system`), message_key, message_params (jsonb, so each viewer sees the alert rendered in **their own** language), acknowledged_by, acknowledged_at, created_at.

**Mobile sync**
- `sync_batches`: id, user_id, device_id, received_at, incident_count, status, error. The deduplication key is `incidents.client_uuid` (SRS §3.4.4).

**Reports**
- `incident_reports`: id, incident_id (unique), generated_at, generated_by, pdf_media_id, language, narrative (text, nullable; LLM or template), stats (jsonb).

**Training**
- `training_scenarios`: id, title_en, title_ur, description_en, description_ur, difficulty, kind (`zone|posture|mixed`), is_active, is_placeholder, created_by.
- `scenario_items`: id, scenario_id, order, media_id, **ground_truth** (jsonb, §9.6), **reference_output** (jsonb: the model output computed through the ML seam and stored, so the trainer works offline from the model), reference_model_version.
- `training_attempts`: id, scenario_id, user_id, started_at, submitted_at, score_pct, feedback (jsonb), llm_feedback (text, nullable).
- `attempt_answers`: id, attempt_id, item_id, answer (jsonb), is_correct, per_target_results (jsonb).

Write `db/seed.py`. It must be idempotent: one station, one user per role, default `system_settings`, placeholder training scenarios (if Q2 is unanswered), and **one demo closed incident** with zones, assessments, victims and alerts so that Reports and the Dashboard have content on first run.

---

## 6. Roles and access (RBAC), from SRS §2.3, §5.3 and §5.5

| Capability | admin | incident_commander | field_responder | training_staff | trainee |
|---|---|---|---|---|---|
| Live dashboard and incidents (create, dispatch, close) | view | ✅ | ❌ | ❌ | ❌ |
| Zone Capture (stream phone camera) and simplified zone map | ❌ | ✅ | ✅ (zones assigned to them, or any zone in an active incident) | ❌ | ❌ |
| Upload thermal images and videos | ❌ | ✅ | ✅ | ❌ | ❌ |
| Incident records, footage and reports (view, PDF) | ✅ | ✅ | ❌ | ❌ | ❌ |
| Team deployment | view | ✅ | own assignment only | ❌ | ❌ |
| Simulation trainer: attempt | ❌ | ✅ | ✅ | ✅ | ✅ |
| Trainer results: own | n/a | ✅ | ✅ | ✅ | ✅ |
| Trainer results: everyone's | ✅ | ✅ (SRS: "get trainee reports") | ❌ | ✅ | ❌ |
| Manage scenarios | ✅ | ❌ | ❌ | ❌ | ❌ |
| Users and roles, system status, audit log, system settings | ✅ | ❌ | ❌ | ❌ | ❌ |
| Delete incident records | ✅ (with confirmation and audit) | ❌ | ❌ | ❌ | ❌ |

Enforce this **on the backend** with a dependency such as `require_roles(...)`; the frontend only hides what the user can't use. Trainees must get `403` on every incident endpoint (SRS §5.5.1).

**Auth details**
- Username and password. Passwords must be at least 8 characters and contain both letters and numbers (SRS §5.5.4). Hash with argon2.
- Access JWT lasts 15 minutes. The refresh token is opaque, rotated on use, stored hashed, and kept in an **httpOnly, Secure, SameSite=Strict cookie** for the web.
- **30-minute idle logout, except during an active incident** (SRS §5.3.1). The frontend idle timer sends a `/auth/heartbeat` while the user is on the live dashboard or capture screen of an `active` incident. The backend allows refresh only if the last activity is under 30 minutes old or the user is the commander or an assignee of an active incident.
- Password reset is admin-only (SRS UC-08 alternative flow 2), and sets `must_change_password`.
- **Mobile offline sign-in support (SRS UC-08 alternative flow 1).** Endpoint `POST /api/v1/auth/mobile/login` returns the tokens **plus** a credential bundle `{user_id, username, role, password_hash, hash_params, issued_at}` that the Flutter app stores in secure storage. `GET /api/v1/auth/mobile/refresh-bundle` returns `410 Gone` if the account is deactivated, so the app wipes it. Add a note to `DECISIONS.md` that shipping the argon2 hash to the device is what the SRS specifies, and use strong argon2 parameters because of it.

---

## 7. API surface

All REST endpoints live under `/api/v1` and are documented in OpenAPI at `/api/docs` (SRS §3.3.8). Every endpoint except login and health requires a token (SRS §5.3.3). Errors use one envelope, `{error: {code, message_key, params}}`, so the frontend can translate them.

### 7.1 REST (minimum set)
- **auth**: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/heartbeat`, `GET /auth/me`, `POST /auth/change-password`, `POST /auth/mobile/login`, `GET /auth/mobile/refresh-bundle`
- **users** (admin): `GET/POST /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/deactivate`, `POST /users/{id}/reset-password`
- **incidents**: `GET /incidents?status=&q=&from=&to=`, `POST /incidents` (creates incident, floors, zones and assignments in one transaction, matching the dispatch modal), `GET /incidents/{id}` (full aggregate: zones with current status, assignments, KPIs), `PATCH /incidents/{id}`, `POST /incidents/{id}/activate`, `POST /incidents/{id}/close` (requires `{"confirm": true}`; triggers report generation), `DELETE /incidents/{id}` (admin, audited)
- **zones**: `GET /incidents/{id}/zones`, `PATCH /zones/{id}`, `GET /zones/{id}/assessments?limit=`
- **teams**: `GET /incidents/{id}/assignments`, `POST /incidents/{id}/assignments`, `DELETE /assignments/{id}` (soft unassign)
- **uploads and analysis**: `POST /incidents/{id}/thermal-uploads` (multipart image or video, optional zone_id) → `{media_id, job_id}`; `GET /jobs/{id}`; `GET /media/{id}` (auth-checked stream, supports Range for video); `GET /media/{id}/thumbnail`
- **detections and victims**: `GET /incidents/{id}/victims` (ranked by RPI), `PATCH /victims/{id}` (mark rescued or false positive), `GET /media/{id}/detections`
- **alerts**: `GET /incidents/{id}/alerts`, `POST /alerts/{id}/ack`
- **reports**: `GET /incidents/{id}/report`, `POST /incidents/{id}/report/regenerate`, `GET /incidents/{id}/report.pdf?lang=en|ur`
- **training**: `GET /training/scenarios`, `GET /training/scenarios/{id}` (**without** ground truth), `POST /training/scenarios/{id}/attempts`, `POST /training/attempts/{id}/submit`, `GET /training/attempts?user_id=` (own, or all for staff and commanders), `GET /training/attempts/{id}` (result with ground truth and reference output revealed)
- **training admin**: `POST/PATCH/DELETE /admin/scenarios…`, `POST /admin/scenarios/{id}/items` (media and ground truth), `POST /admin/scenarios/{id}/recompute-reference` (runs the ML seam over the items)
- **mobile sync**: `POST /sync/incidents` (§7.4)
- **settings**: `GET /settings` (any authenticated user, public subset), `PATCH /admin/settings` (admin, audited)
- **admin**: `GET /admin/status` (DB OK, queue depth, active WS connections, ML backend mode and loaded model versions, disk usage, last backup time), `GET /admin/audit-logs`
- **tts**: `POST /tts` `{text, lang}` → audio. Returns `501` when the provider is `browser`, and the frontend then uses `speechSynthesis`.
- **llm** (only when enabled): `POST /assist/help` `{question, lang, page}`
- **health**: `GET /health`, `GET /health/ready`

### 7.2 WebSocket: commander and incident stream `wss://…/ws/incidents/{incident_id}`
Authenticate with the access token in the first message (`{"type":"auth","token":…}`), not in the URL. The server pushes:
```jsonc
{"type":"zone.updated","zone_id":"…","status":"unsafe","risk_score":0.71,"confidence":0.82,"assessment_id":"…","frame_url":"/api/v1/media/…","at":"…"}
{"type":"alert.created","alert":{…}}               // includes message_key + params
{"type":"victim.upserted","victim":{…}}            // ranked list re-sorted client-side
{"type":"assignment.changed","assignment":{…}}
{"type":"incident.updated","incident":{…}}         // status, KPIs
{"type":"job.progress","job_id":"…","progress":0.4}
{"type":"capture.session","session":{…,"state":"started|ended"}}
```
The client reconnects automatically with backoff. After reconnecting it refetches the incident aggregate. While disconnected it shows the **last known state** with a "connection lost, showing last update at HH:MM" banner (SRS UC-07 exceptional flow).

### 7.3 WebSocket: zone capture `wss://…/ws/capture`
1. The client sends `{"type":"auth","token":…}`, then `{"type":"start","incident_id":…,"zone_id":…}`. The server creates a `capture_session` and replies `{"type":"started","session_id":…,"target_fps":1}`.
2. The client sends **binary JPEG frames** (rear camera via `getUserMedia({video:{facingMode:"environment"}})`, drawn to a canvas, roughly 960px wide, quality 0.7) at `target_fps`. `target_fps` is configurable and defaults to 1 fps, because the SRS needs a zone update within 6 seconds.
3. The server keeps **only the latest frame per session** (latest-frame-wins; never queue a backlog), runs the zone pipeline (§9.3), stores the frame plus the assessment, updates the zone, publishes `zone.updated` to the incident channel, and replies on this socket: `{"type":"zone_result","status":…,"reasons":[…],"overlay_url":…}`.
4. On rapid change, or when a zone becomes unsafe or blocked, the server also sends `{"type":"alert", …}`. The capture screen **speaks** it in the user's language, for example "Zone F1-Z3 is unsafe. Turn back."
5. `{"type":"stop"}` or a disconnect ends the session.

Backend capacity target: **5 concurrent capture sessions plus 10 logged-in users** (SRS §5.1.2). Run model inference in a thread or process pool so it never blocks the event loop.

### 7.4 Mobile sync contract `POST /api/v1/sync/incidents`
This is idempotent per `client_uuid`. The Flutter app is not part of this handoff, but **this contract is**. Document it in `docs/API.md` with a sample payload, and write tests for it.
```jsonc
{
  "device_id": "android-…",
  "app_version": "1.0.0",
  "incidents": [{
    "client_uuid": "c0b4…",              // dedupe key
    "started_at": "…", "ended_at": "…",
    "label": "optional free text", "linked_incident_id": null,  // optional link to a web incident
    "detections": [{
      "client_detection_uuid": "…", "captured_at": "…", "mode": "live|still",
      "track_id": 3, "bbox": [x1,y1,x2,y2],          // normalised 0–1
      "keypoints": [[x,y,c], …17],                    // optional
      "posture": "lying", "posture_confidence": 0.81, "low_confidence": false,
      "detection_confidence": 0.88, "env_risk": 0.0,
      "rpi_score": 0.86, "rpi_band": "critical",
      "frame_ref": "frame_0012.jpg"                   // optional, matches a multipart part
    }]
  }]
}
```
- Accept `application/json`, **or** `multipart/form-data` with a `payload` JSON part plus optional thermal frame image parts referenced by `frame_ref`.
- Response: `{"results":[{"client_uuid":…,"status":"created|duplicate|error","incident_id":…,"error":null}]}`. A duplicate returns `200` with `duplicate`, so the phone marks it as sent.
- **Recompute RPI on the server** with the current settings, and keep the mobile-sent value in `meta.mobile_rpi` so the two can be compared.

---

## 8. Domain logic you implement fully (not ML, real code)

### 8.1 Rescue Priority Index (`services/rpi.py`), SRS §4.3
```
RPI = w_p · P(posture) + w_c · C(detection_confidence) + w_r · R(env_risk)
```
- Default `P`: lying = 1.0, bending = 0.6, sitting = 0.5, standing = 0.2. If posture is `low_confidence`, apply a configurable factor (default 0.9 × P), still rank the person, and show the flag.
- `C` is the detection confidence (0–1). `R` is the environmental risk (0–1) and **defaults to 0 when unavailable**. The weight must accept 0 (SRS §4.3 REQ-5, §5.5.2).
- Default weights: `w_p = 0.6`, `w_c = 0.25`, `w_r = 0.15`. If `R` is unavailable, compute RPI from posture and confidence only (SRS UC-03 alternative flow 2).
- Bands (SRS REQ-2 names four): critical ≥ 0.75, high ≥ 0.55, medium ≥ 0.35, otherwise low. **Colour mapping:** critical and high are red, medium is yellow, low is green, always with the band label. This keeps the SRS's red/yellow/green and its four bands consistent; record that in `DECISIONS.md`.
- For web uploads, environmental risk comes from the **current status of the zone** the upload is tagged with: unsafe or blocked = 1.0, caution = 0.5, safe = 0.0, unclassified = unavailable. Later the thermal model integrator can replace this with readings from raw temperature data.
- Every value is in `system_settings` and editable by an admin. Write unit tests for the edge cases.

### 8.2 Zone risk fusion (`services/zone_fusion.py`), SRS §4.5
Inputs are the building-element segmentation (pixel share per class) and the damage instances (class, mask area, which element they overlap). It returns `{status, risk_score, confidence, analysable, reasons[]}`.

Default heuristic (thresholds in settings; record in `DECISIONS.md` that these must be tuned):
- **Not analysable** if the models return low confidence or too little visible structure (for example less than 15% of the frame is recognised building elements, as with heavy smoke). In that case **keep the zone's previous status and never set it to safe**. Log an `analysis_failed` info alert at most once per minute per zone (SRS UC-05 exceptional flow 2).
- **blocked** if `collapse` or `debris` covers at least 25% of the floor or door region, or more than 35% of the frame (SRS UC-05 alternative flow 2).
- **unsafe** if any `collapse` instance with confidence of at least 0.5, or crack and spalling area on walls, columns or ceiling of at least 5%.
- **caution** if any structural-damage instance has confidence of at least 0.4.
- **safe** otherwise.
- **Stale rule:** if `now − status_updated_at` exceeds `stale_zone_seconds` (default 120), the API and UI present the zone as `unclassified` (stale). **A zone is never shown as safe without a current analysis** (SRS §5.2.3, §5.5.2).
- **Rapid-change alert:** a transition from safe (or caution) to unsafe or blocked within `rapid_change_window_s` (default 60) raises a `crit` alert. Any transition into unsafe or blocked raises at least a `warn` alert (SRS UC-05 exceptional flow 1, REQ-6).

### 8.3 Tracking for thermal video (`services/tracking.py`)
When the backend analyses an uploaded thermal video, it **samples 2 frames per second** (SRS REQ-7). It runs the pose detector on each sampled frame and uses a simple IoU plus centroid tracker. A person is confirmed only after appearing in **2 or more consecutive samples**, and short misses don't drop the track (SRS UC-01 alternative flow 3). It then aggregates into `victims`, takes the highest-RPI observation as the best one, and pushes `victim.upserted` events as it goes. Still images are analysed once.

### 8.4 Voice guidance (web)
Spoken alerts use **templates, not an LLM**, because they must be fast (under 2 s, SRS §5.1.1) and predictable. Define message keys in `i18n/{en,ur}.json`, for example `voice.zone_unsafe`: "Zone {{zone}} is unsafe. Turn back." and `voice.victim_critical`: "Critical victim detected in zone {{zone}}." `lib/tts.ts` picks a voice by language, queues and de-duplicates messages, and **shows the text on screen when TTS is unavailable** (SRS UC-04 exceptional flow). Speak on the commander dashboard (critical alerts, if enabled in settings) and on the responder capture screen. The browser must not take over or block other audio.

### 8.5 Reports (`services/reports.py`)
On **close**, compile and store the report (SRS §4.7 REQ-4): incident details, timeline, team assignments, final and peak zone status per zone, the zone history chart, the ranked victim list (web and mobile sources), alerts, representative frames, and the model versions used. Generate the PDF in **English or Urdu** (embed Noto Nastaliq Urdu or Noto Naskh for the Urdu PDF, with RTL). The narrative paragraph comes from a template, or from the LLM if enabled. **Always include the disclaimer** that the system is decision support only, and that low or absent detections don't guarantee nobody is present (SRS §5.2.3).

---

## 9. ML seam: the part left for model integration

**Rule: nothing outside `app/ml/` imports torch, ultralytics or transformers.** Everything else depends only on `contracts.py`. This satisfies SRS §5.4.3: "a model can be swapped without changing UI code."

### 9.1 `ml/contracts.py`
```python
from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence
import numpy as np

Posture = Literal["standing", "sitting", "lying", "bending"]

@dataclass
class PersonDetection:
    bbox: tuple[float, float, float, float]      # normalised x1,y1,x2,y2 in [0,1]
    detection_confidence: float
    posture: Posture
    posture_confidence: float
    keypoints: list[tuple[float, float, float]] | None = None  # 17 COCO kpts (x,y,conf), normalised

class ThermalPoseDetector(Protocol):
    name: str; version: str
    def load(self) -> None: ...
    def predict(self, image_rgb: np.ndarray, temperature_c: np.ndarray | None = None) -> list[PersonDetection]: ...
    # image_rgb: HxWx3 uint8 (colourised thermal); temperature_c: HxW float32 if available

ElementClass = Literal["wall", "floor", "ceiling", "door", "window", "column", "stairs", "other"]

@dataclass
class ElementSegmentation:
    class_map: np.ndarray                         # HxW uint8 index into `classes`
    classes: dict[int, ElementClass]
    confidence: float                             # mean max-softmax or similar
    def share(self) -> dict[ElementClass, float]: ...   # implement in contracts (pixel fraction)

class BuildingElementSegmenter(Protocol):        # SegFormer-B2 (ADE20K-based)
    name: str; version: str
    def load(self) -> None: ...
    def predict(self, image_rgb: np.ndarray) -> ElementSegmentation: ...

DamageClass = Literal["crack", "spalling", "exposed_rebar", "collapse", "debris"]

@dataclass
class DamageInstance:
    cls: DamageClass
    confidence: float
    mask: np.ndarray                              # HxW bool
    polygon: list[tuple[float, float]] = field(default_factory=list)  # normalised, for the UI overlay

class StructuralDamageSegmenter(Protocol):       # YOLO-seg (Φ-Net / SDNET2018-based)
    name: str; version: str
    def load(self) -> None: ...
    def predict(self, image_rgb: np.ndarray) -> list[DamageInstance]: ...
```
Fusion (§8.2) consumes `ElementSegmentation` plus `list[DamageInstance]`. It is ordinary application code, not a model.

### 9.2 `ml/registry.py`
`ML_BACKEND=mock|real` comes from the env, along with `THERMAL_POSE_WEIGHTS`, `SEGFORMER_WEIGHTS`, `DAMAGE_SEG_WEIGHTS` and `ML_DEVICE=cpu|cuda`. Models are loaded once at startup, the loaded `name` and `version` are reported in `/admin/status`, and `model_versions` is stored on every assessment and detection. If `real` fails to load, the app **refuses to start** with a clear error message rather than silently falling back. An explicit `ML_ALLOW_MOCK_FALLBACK=true` allows falling back.

### 9.3 Pipelines (application code that calls the seam)
- `jobs/thermal_pose_job.py`: image or video → frames (2 fps) → `ThermalPoseDetector.predict` → tracking → RPI → persist → events.
- `services/zone_pipeline.py`: RGB frame → `BuildingElementSegmenter` and `StructuralDamageSegmenter` (in parallel, in a thread pool) → fusion → persist the assessment, the frame, and an **overlay PNG** (element colours plus damage polygons) → events and alerts.

### 9.4 Mocks (`ml/mock/`), the default
- These must be **deterministic** given the input (seed from a hash of the downsampled image), so tests are stable. They must also be **plausible** in a live demo, for example by drifting slowly over time per zone, so that zones move through safe, caution and unsafe states.
- The mock pose detector returns 0–3 people with sensible boxes, keypoints and a posture mix. The mock segmenter returns block-shaped regions of wall, floor and ceiling. The mock damage model sometimes returns a crack or debris polygon.
- Add a dev-only toggle `MOCK_SCENARIO=calm|escalating|collapse` to force demo storylines.

### 9.5 Real stubs (`ml/real/`)
These are the classes `UltralyticsThermalPose`, `SegFormerB2Segmenter` and `YoloDamageSegmenter`. Each `load()` and `predict()` **raises `NotImplementedError`**, with a docstring that states exactly what to implement: expected weight format (`.pt` / HF folder / ONNX), preprocessing (input size, normalisation), output conversion to the contract, and a **class-name mapping table** to fill in (for example ADE20K's 150 classes → `ElementClass`, and the trained YOLO-seg classes → `DamageClass`). Also add `backend/tests/ml/test_contract_conformance.py`, which runs any registered implementation against sample images and checks output shapes, ranges and types. **This test is the acceptance test for whoever integrates the models.**

### 9.6 Simulation trainer (built fully, uses the stored reference output)
**Ground-truth format** (stored in `scenario_items.ground_truth`; share this with the owner when asking Q2):
```jsonc
{
  "type": "zone",                       // or "posture"
  // zone item: the image/video frame is split into regions (grid or polygons) the trainee labels
  "regions": [{"id":"r1","polygon":[[0,0],[0.5,0],[0.5,1],[0,1]],"status":"unsafe"}, …],
  // posture item: each person to classify
  "people": [{"id":"p1","bbox":[0.2,0.3,0.4,0.9],"posture":"lying"}, …],
  "explanation_en": "Visible spalling on the column…", "explanation_ur": "…"
}
```
- **Trainee flow** (SRS UC-06): pick a scenario, see each item (image or video with play/pause), label every region's zone status and every person's posture (big tap targets, bilingual), and submit. The result page shows the trainee's answer next to the **ground truth** and the **model's reference output**, gives a per-target correct/incorrect verdict and an overall score, and shows the explanation (plus LLM feedback if enabled). Trainees can retry (SRS UC-06 alternative flow).
- **Grading:** a target is correct if it exactly matches the ground truth. Optionally give partial credit for adjacent severity (caution vs unsafe = 0.5), configurable.
- Scoring is against the **ground truth**. The model's output is shown for comparison, as the SRS asks ("compare their decisions with the model's"). Show the agreement between trainee and model as a secondary metric.
- An item with no reference output is unusable (SRS UC-06 exceptional flow), so hide it until `recompute-reference` has been run.
- Staff and commander view: a table of all trainees' attempts with filters and a per-trainee progress chart.
- Admin: create and edit scenarios, upload media, and enter ground truth with an **in-browser labelling tool** (draw region polygons or grid cells, draw person boxes, pick labels).

---

## 10. LLM integration (optional, behind an interface)

`app/llm/` contains a `LLMProvider` protocol (`complete(system, messages, max_tokens, lang) -> str`) with these implementations: `TemplateProvider` (default; no network), and whichever provider the owner picks in Q3. Configuration is through `LLM_PROVIDER`, `LLM_MODEL` and `LLM_API_KEY` in `.env`, and the key is never logged.

Uses, each **behind a feature flag and always with a template fallback**:
1. **Incident report narrative** (EN and UR), generated from the structured stats only, never inventing facts. The prompt says to use only the numbers provided.
2. **Trainer feedback**: explains *why* the trainee's label differs from the ground truth, using the explanation fields and model reasons.
3. **In-app help assistant**: answers "how do I…" questions grounded in the Help pages content (send the relevant page text as context).

**Never** use the LLM for alerts, voice guidance, zone status or RPI. Those stay deterministic.

---

## 11. Frontend: route map and key behaviours

| Route | Roles | Content |
|---|---|---|
| `/` splash → `/signin` → `/language` (first time) → `/onboarding` (first time) | all | As in the prototype. Remember the language choice. |
| `/live` | commander, admin (read) | Empty, briefing and live states (§4.2). Pick from active incidents if there are several. |
| `/incidents/new` (modal on `/live`) | commander | Dispatch form → `POST /incidents`. |
| `/incidents/:id/team` | commander | Assign and reassign responders to zones; show history. |
| `/capture` | responder, commander | **Mobile-first.** Choose incident and zone (assigned zones first). A big START/STOP button. A camera preview with the overlay of the latest result. A large status chip ("UNSAFE" plus colour plus icon). A compact zone map. Spoken alerts. Camera and internet indicators. A screen wake lock while capturing. |
| `/analysis` | commander, responder | Drag-and-drop thermal image or video, tagged to an incident and zone. Job progress. Viewer with boxes, posture labels, RPI chips and a low-confidence flag. Video scrubber with per-frame detections. |
| `/reports`, `/reports/:incidentId` | commander, admin | List and detail; PDF download (EN/UR); media gallery; zone history chart. |
| `/trainer`, `/trainer/:scenarioId`, `/trainer/attempts/:id`, `/trainer/results` | per §6 | §9.6. |
| `/admin/users`, `/admin/scenarios`, `/admin/settings`, `/admin/status`, `/admin/audit` | admin | Includes confirmation dialogs. |
| `/settings` | all | Language, voice on/off and voice choice, sound alerts, replay onboarding. |
| `/help`, `/help/:topic` | all | Bilingual Markdown help pages per screen. The `?` button on each screen deep-links to its topic. |

Global behaviours: the shell has a language switch, Help, an internet indicator (`navigator.onLine` plus WS state) and a camera indicator on camera screens. RTL comes from `document.documentElement.dir`, and CSS uses **logical properties** (`margin-inline-start`, etc.). Switching language keeps state. Every async action has loading, empty and error states. Errors use translated, actionable text. Use 48px touch targets at widths of 768px and below. Test layouts at 360, 768, 1280 and 1920 px.

Camera on the web: this needs **HTTPS** (Caddy in Docker; Vite dev server with `@vitejs/plugin-basic-ssl` or mkcert). Detect and explain these failures in clear language: permission denied, no camera, insecure context, camera in use by another app (SRS §2.4.5).

---

## 12. Non-functional checklist (verify each one before calling it done)

- [ ] Uploaded thermal image results in **5 s or less** after the upload finishes (mock backend; also log real-backend timings) (SRS §5.1.1).
- [ ] Zone map updated **within 6 s** of a frame reaching the server.
- [ ] Pages and sign-in respond in **3 s or less** with 10 concurrent users. Add a small `locust` or `k6` script under `backend/loadtest/`.
- [ ] 5 concurrent capture sessions sustained (load-test script that simulates WS clients sending JPEGs).
- [ ] HTTPS and WSS only behind Caddy. Security headers set. CORS locked to the frontend origin.
- [ ] Passwords hashed with argon2. Password rules enforced. Every endpoint except login and health requires auth. RBAC tests for every router (especially trainee → incidents = 403).
- [ ] Every admin change and deletion is in `audit_logs`.
- [ ] Daily `pg_dump` backup container with 7-day rotation, and a documented restore command.
- [ ] Data at rest: document in `docs/DEPLOYMENT.md` that encryption at rest is handled with an encrypted volume or disk at deployment (SRS §5.3.2).
- [ ] The backend restarts cleanly (`restart: unless-stopped`). The frontend reconnects its WebSockets and resumes the capture session without signing in again (SRS §5.2.2).
- [ ] An unanalysed or stale zone is **never** displayed as safe (write a frontend test and a backend test for this).
- [ ] Every colour has a text label. Urdu RTL renders correctly on every route (add a Playwright screenshot pass in both languages).
- [ ] OpenAPI docs are reachable. `docs/API.md` covers the WS and mobile sync contracts.

---

## 13. Build order (phases with exit criteria)

Work in this order and commit at the end of each phase. Keep a task list. After each phase, run the tests and fix failures before moving on.

1. **Phase 0, setup and questions.** Ask §0. Scaffold the monorepo, Docker Compose (db, backend, frontend, caddy), `.env.example`, lint and format, and CI (GitHub Actions: lint, test, build). *Exit:* `docker compose up` serves an HTTPS "hello" page and `/api/v1/health`.
2. **Phase 1, database, auth and RBAC.** Models, Alembic, seed, the auth flows (§6), users admin and audit. *Exit:* pytest covers login, refresh rotation, idle-timeout rules, mobile bundle and RBAC matrix.
3. **Phase 2, frontend shell.** Tokens, fonts, i18n plus RTL, splash, sign-in, language and onboarding, sidebar by role, indicators, Help skeleton, typed API client. *Exit:* you can log in as each role and see the right navigation in both languages.
4. **Phase 3, incidents, zones and teams.** Dispatch modal, the three live-dashboard states, team page, incident WS channel, alerts service, KPIs, donut, evacuation bar. *Exit:* a commander creates an incident; a second browser sees updates live.
5. **Phase 4, ML seam, mocks and zone capture.** Contracts, registry, mocks, zone pipeline plus fusion, the `/capture` page with real phone camera over WSS, overlays, spoken alerts. *Exit:* on a phone over LAN HTTPS, streaming a zone changes its colour on the commander's dashboard within 6 s; rapid change fires a critical alert that is spoken.
6. **Phase 5, thermal uploads and victims.** Upload, job queue, video sampling, tracking, RPI, ranked victims, viewer. Mobile sync endpoint plus tests. *Exit:* uploading a video produces a ranked victim list on the dashboard; a sync payload posted twice is created once.
7. **Phase 6, reports.** Close incident with confirmation, report compile, EN and UR PDFs, reports pages, optional LLM narrative. *Exit:* the closed demo incident downloads a correct PDF in both languages.
8. **Phase 7, simulation trainer.** Scenarios, labelling tool, reference recompute, trainee flow, grading, results views, optional LLM feedback. *Exit:* a trainee completes a scenario and sees the comparison; staff see all results.
9. **Phase 8, admin, settings and help.** Settings editor (RPI, fusion and thresholds with validation), status page, audit viewer, help content (EN and UR) for every screen.
10. **Phase 9, hardening.** Load tests, Playwright end-to-end run (§14), the accessibility pass, `MODEL_INTEGRATION.md`, `DEPLOYMENT.md`, README quick start.

---

## 14. Definition of done: end-to-end demo script (all with mock models)

Write this as a Playwright test plus a human-readable `docs/DEMO.md`:
1. `docker compose up -d && docker compose exec backend python -m app.db.seed` gets the app running on `https://localhost`.
2. Admin logs in, creates a commander and two responders, sets the language to Urdu, and confirms the UI is right to left.
3. Commander logs in and logs an emergency: 2 floors × 4 zones, both responders assigned. The briefing state appears.
4. Responder (second browser, mobile viewport) opens `/capture`, picks their zone and starts streaming (use Playwright's fake camera: `--use-fake-device-for-media-stream`). The commander sees the zone go from unclassified to a classified state. With `MOCK_SCENARIO=escalating`, a critical alert fires and is shown and spoken.
5. Commander uploads a thermal video tagged to a zone. Progress shows, then ranked victims appear, with the critical ones at the top.
6. A mobile sync payload is posted (a test helper). Its victims appear under source "mobile".
7. Commander closes the incident after confirming. The report appears, and the EN and UR PDFs download.
8. Trainee completes a scenario and sees a score with the comparison against the model. Training staff see the trainee's attempt.
9. A trainee calling `GET /api/v1/incidents` gets 403.
10. `/admin/status` shows `ML backend: mock` with the model versions.

**When all of this passes, the only remaining work is §9.5:** implement the three real model adapters, place the weights, set `ML_BACKEND=real`, and pass `test_contract_conformance.py`. `docs/MODEL_INTEGRATION.md` must spell out exactly that: files to edit, weight locations, class-mapping tables to fill, expected input sizes, how to benchmark the latency targets, and how to recompute trainer reference outputs after a model update.

---

## 15. Out of scope for this handoff
- The Flutter mobile app, the thermal camera (UVC/Kotlin) integration, and on-device TFLite. Only the **server side** of mobile sync and auth is in scope.
- Training or fine-tuning any model.
- Choosing production hosting (it is TBD in the SRS). Provide Docker plus docs only.
