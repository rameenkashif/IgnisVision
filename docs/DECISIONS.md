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
