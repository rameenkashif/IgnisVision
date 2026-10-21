# Ignis Vision — Web App

AI fire-incident response for **Rescue 1122**: incident command dashboard, live zone-risk analysis from phone cameras, thermal upload analysis with Rescue Priority Index, simulation trainer, and reports — in English and Urdu.

- **Brief:** [`HANDOFF.md`](HANDOFF.md) · **Decisions:** [`docs/DECISIONS.md`](docs/DECISIONS.md)
- **Requirements:** `docs/reference/Ignis-Vision-SRS-2.0.docx` (`pandoc -t plain` to read) · **Visual reference:** `docs/reference/ignis_vision_dashboard.html`

Stack: React 18 + TS + Vite · FastAPI (Python 3.11) · PostgreSQL 16 · Caddy · Docker Compose.

## Quick start

```bash
cp .env.example .env        # then set POSTGRES_PASSWORD and JWT_SECRET
docker compose up -d --build
```

Create the demo station, accounts and default settings (idempotent; migrations run automatically on backend start):

```bash
docker compose exec backend python -m app.db.seed          # prints the demo password
# or choose it: docker compose exec -e SEED_PASSWORD=YourPass123 backend python -m app.db.seed
```

Demo accounts (one per role): `admin`, `commander1`, `responder1`, `trainee1`, `trainer1`. The seed also adds a closed demo incident with its report and three PLACEHOLDER training scenarios.

Open **https://localhost**. For a demo storyline (safe → caution → unsafe while capturing) set `MOCK_SCENARIO=escalating` in `.env`. Health: `https://localhost/api/v1/health`, readiness (checks DB): `/api/v1/health/ready`, API docs: `/api/docs`.

Caddy uses its own local CA (`tls internal`), so the browser warns the first time. To trust it:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
# macOS:   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt
# Linux:   sudo cp caddy-root.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates
```

### Testing the phone camera over Wi-Fi

`getUserMedia` needs HTTPS. Set `SITE_ADDRESS` to this machine's LAN IP (e.g. `192.168.1.20`) and `CORS_ORIGINS=["https://192.168.1.20"]` in `.env`, run `docker compose up -d`, then install `caddy-root.crt` (above) on the phone (iOS: AirDrop it → Settings → Profile → install, then Settings → General → About → Certificate Trust Settings; Android: Settings → Security → Install certificate → CA). Alternatively use [mkcert](https://github.com/FiloSottile/mkcert) (`mkcert 192.168.1.20`, mount the files into the caddy container, and replace `tls internal` with `tls /certs/cert.pem /certs/key.pem`).

### AI-drafted text (optional)

Reports always get a template narrative in English and Urdu. To have Claude rewrite it from the recorded facts, set `LLM_PROVIDER=anthropic` and `LLM_API_KEY=…` in `.env` (never commit it), restart the backend, and turn on `llm.features.report_narrative` (admin: `PATCH /api/v1/admin/settings`; the admin screen arrives in Phase 8). Trainer feedback works the same way with `llm.features.trainer_feedback`. If the API is unreachable the template text is kept, and scores never depend on the LLM.

## Development

```bash
# DB + backend with hot reload (ports 5432, 8000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db backend

# Frontend dev server (HTTPS on :5173, proxies /api and /ws to :8000)
cd frontend && npm install && npm run dev
```

Checks (same as CI):

```bash
# backend tests need a disposable Postgres; its schema is dropped and rebuilt each run
docker run -d --name ignis-testdb -e POSTGRES_USER=ignis -e POSTGRES_PASSWORD=ignis -e POSTGRES_DB=ignis -p 5433:5432 postgres:16-alpine
cd backend  && pip install -r requirements-dev.txt && ruff check . && black --check . \
  && DATABASE_URL=postgresql+asyncpg://ignis:ignis@localhost:5433/ignis pytest -q
cd frontend && npm ci && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

New migration after changing models:

```bash
cd backend && DATABASE_URL=… alembic revision --autogenerate -m "describe change" && alembic upgrade head
```

End-to-end tests (Playwright) run against the Docker stack:

```bash
docker compose exec -e SEED_PASSWORD=Demo-pass-1234 backend python -m app.db.seed --reset-passwords
cd frontend && npx playwright install chromium && E2E_PASSWORD=Demo-pass-1234 npm run e2e
```

After changing backend endpoints, regenerate the typed client (CI fails if you forget):

```bash
cd backend && python scripts/export_openapi.py && cd ../frontend && npm run gen:api
```

API conventions and auth flows: [`docs/API.md`](docs/API.md).

## Backups

The `backup` service writes a `pg_dump` to `./backups/` daily and keeps 7 days. Restore:

```bash
docker compose exec -T db pg_restore -U ignis -d ignis --clean --if-exists < backups/ignis-<timestamp>.dump
```

## Status

Phase 0 (scaffold, Docker, HTTPS, CI) Phase 1 (database schema, auth, RBAC, user admin, audit, settings) Phase 2 (frontend shell: splash, sign-in, language + RTL, onboarding, role-based navigation, indicators, help skeleton, settings) Phase 3 (incidents, zones, teams, alerts, live dashboard, WebSocket channels) Phase 4 (ML seam with mock models, zone risk fusion, phone zone capture, spoken alerts) Phase 5 (thermal image/video uploads, job queue, tracking, Rescue Priority Index, ranked victims, mobile sync) Phase 6 (incident reports, EN/UR PDF export, optional AI-drafted narrative) and Phase 7 (simulation trainer: placeholder scenarios, labelling tool, reference outputs through the model seam, grading, results and progress views, optional AI feedback) complete. Model integration: [`docs/MODEL_INTEGRATION.md`](docs/MODEL_INTEGRATION.md). See `HANDOFF.md` §13 for the phase plan.
