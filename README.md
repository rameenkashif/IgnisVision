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

Open **https://localhost**. Health: `https://localhost/api/v1/health`, readiness (checks DB): `/api/v1/health/ready`, API docs: `/api/docs`.

Caddy uses its own local CA (`tls internal`), so the browser warns the first time. To trust it:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
# macOS:   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt
# Linux:   sudo cp caddy-root.crt /usr/local/share/ca-certificates/ && sudo update-ca-certificates
```

### Testing the phone camera over Wi-Fi

`getUserMedia` needs HTTPS. Set `SITE_ADDRESS` to this machine's LAN IP (e.g. `192.168.1.20`) and `CORS_ORIGINS=["https://192.168.1.20"]` in `.env`, run `docker compose up -d`, then install `caddy-root.crt` (above) on the phone (iOS: AirDrop it → Settings → Profile → install, then Settings → General → About → Certificate Trust Settings; Android: Settings → Security → Install certificate → CA). Alternatively use [mkcert](https://github.com/FiloSottile/mkcert) (`mkcert 192.168.1.20`, mount the files into the caddy container, and replace `tls internal` with `tls /certs/cert.pem /certs/key.pem`).

## Development

```bash
# DB + backend with hot reload (ports 5432, 8000)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db backend

# Frontend dev server (HTTPS on :5173, proxies /api and /ws to :8000)
cd frontend && npm install && npm run dev
```

Checks (same as CI):

```bash
cd backend  && pip install -r requirements-dev.txt && ruff check . && black --check . && pytest -q
cd frontend && npm ci && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Backups

The `backup` service writes a `pg_dump` to `./backups/` daily and keeps 7 days. Restore:

```bash
docker compose exec -T db pg_restore -U ignis -d ignis --clean --if-exists < backups/ignis-<timestamp>.dump
```

## Status

Phase 0 (scaffold, Docker, HTTPS, CI) complete. See `HANDOFF.md` §13 for the phase plan.
