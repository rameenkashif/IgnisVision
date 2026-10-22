# Deployment

Ignis Vision ships as a Docker Compose stack: **Caddy** (HTTPS/WSS, security headers) → **frontend** (static React build) and **backend** (FastAPI, models, job queue) → **PostgreSQL**, plus a **backup** container. Production hosting is not decided in the SRS; this guide covers a single server (on-premises at a Rescue 1122 station or a VPS).

## 1. Server

| | Minimum (mock models, demo) | Recommended (real models) |
|---|---|---|
| CPU / RAM | 2 cores / 4 GB | 4–8 cores / 16 GB, or an NVIDIA GPU (`ML_DEVICE=cuda`) |
| Disk | 20 GB | 200 GB+ SSD (videos and frames grow with use) on an **encrypted volume** (§5) |
| OS | Any Linux with Docker Engine 24+ and the Compose plugin | Ubuntu 22.04/24.04 LTS |

Measured on a 4-core, 16 GB machine with mock models (`backend/loadtest/run.py`, 60 s, 10 users plus 5 capture sessions at once): pages p95 ≤ 0.13 s, sign-in p50 0.37 s and p95 2.4 s (all 10 signing in at the same instant), frame → commander map p95 0.32 s, thermal image → results 0.12 s. Re-run it on the target server with the real models (§8).

## 2. Install

```bash
git clone <repo> ignis-vision && cd ignis-vision
cp .env.example .env
# Edit .env: POSTGRES_PASSWORD, JWT_SECRET (both long random values), SITE_ADDRESS, CORS_ORIGINS
python3 -c "import secrets;print(secrets.token_urlsafe(48))"   # for JWT_SECRET
docker compose up -d --build
docker compose exec backend python -m app.db.seed   # prints the demo password once
```

Migrations run automatically when the backend starts. The seed is idempotent; on a real deployment, sign in as `admin`, create the real accounts under **Administration → Users**, then deactivate the demo accounts.

With `ENVIRONMENT=prod` the backend refuses to start with the example `JWT_SECRET`.

## 3. Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `SITE_ADDRESS` | Hostname or IP Caddy serves (`localhost`, a LAN IP, or a public domain). |
| `CORS_ORIGINS` | JSON list of browser origins, e.g. `["https://ignis.example.pk"]`. Must match `SITE_ADDRESS`. |
| `POSTGRES_USER/PASSWORD/DB` | Database credentials (internal network only; the DB port is not published). |
| `ENVIRONMENT` | `prod` in production. |
| `JWT_SECRET` | Signs access tokens. Changing it signs everyone out. |
| `REPORT_TIMEZONE` | Time zone printed in PDF reports (default `Asia/Karachi`). |
| `ML_BACKEND`, `ML_DEVICE`, `*_WEIGHTS`, `ML_WORKERS`, `ML_ALLOW_MOCK_FALLBACK` | Models: see `docs/MODEL_INTEGRATION.md`. |
| `MOCK_SCENARIO` | Demo storyline for mock models (`calm` in production). |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` | Optional AI text features (`template` = off). Keep the key only in `.env`; it is never logged. |
| `BACKUP_RETENTION_DAYS` | Daily database dumps kept (default 7). |
| `RETENTION_INTERVAL_S` | How often the data-retention job runs (default 3600). The retention period itself is set in the app. |

Operational thresholds (zone fusion, RPI, timings, data retention, AI features, trainer grading) are edited in **Administration → System settings** and audited.

## 4. HTTPS

Camera access and secure WebSockets need HTTPS everywhere.

- **Public domain (VPS):** point DNS at the server, set `SITE_ADDRESS=ignis.example.pk`, and in `Caddyfile` replace `tls internal` with `tls you@example.pk`. Caddy obtains and renews a Let's Encrypt certificate (ports 80 and 443 must be reachable).
- **Station LAN, no domain:** keep `tls internal` and install Caddy's root certificate on every PC and phone once (README, "Testing the phone camera over Wi-Fi"), or use certificates from your own CA / `mkcert` with `tls /certs/cert.pem /certs/key.pem`.

Caddy sends HSTS, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, a `Permissions-Policy` that allows only the camera, and a strict Content-Security-Policy. Only ports 80/443 should be open in the firewall.

## 5. Data at rest (SRS §5.3.2)

The application does not encrypt files itself. **Put the Docker data directory (or at least the `pgdata` and `media` volumes and `./backups`) on an encrypted disk:**

- On-premises: full-disk encryption (LUKS on Linux, BitLocker on a Windows host), unlocked at boot by an administrator or TPM.
- Cloud: an encrypted block volume (e.g. provider-managed keys) for `/var/lib/docker` and the repository directory.

Copies of backups taken off the server must be encrypted too (e.g. `gpg --symmetric` or an encrypted object store).

## 6. Backups and restore

The `backup` service runs `pg_dump` daily into `./backups/` and keeps `BACKUP_RETENTION_DAYS` days. **Administration → System status** shows the newest backup and warns when it is older than 36 hours. Media files live in the `media` volume; back it up with your usual tooling, or accept that only the database (reports, assessments, detections, accounts) is restorable.

```bash
# Restore the database from a dump (stops nothing; take the app offline first if possible)
docker compose exec -T db pg_restore -U ignis -d ignis --clean --if-exists < backups/ignis-<timestamp>.dump
# Media volume backup example
docker run --rm -v ignis-vision_media:/data -v "$PWD":/out alpine tar czf /out/media-$(date +%F).tgz -C /data .
```

Copy `./backups` off the server regularly (encrypted, §5). Test a restore at least once.

## 7. Data retention

Off by default. When **Administration → System settings → Data retention** is set (days), an hourly job removes closed or deleted incidents older than that, with their media, reports and detections; open incidents are never removed. Each run is recorded in the audit log. Preview or run it by hand:

```bash
docker compose exec backend python -m app.services.retention --dry-run
docker compose exec backend python -m app.services.retention
```

## 8. Monitoring and checks

- `GET /api/v1/health` (liveness) and `/api/v1/health/ready` (database) for external monitoring.
- **Administration → System status**: models, jobs, disk, backups, AI and sessions with warnings.
- Logs: `docker compose logs -f backend` (the LLM key and passwords are never logged).
- Performance on the target hardware: `cd backend && .venv/bin/python loadtest/run.py --base https://<site> --password <pw> --ca caddy-root.crt` (exit code 0 = all targets met) and `docker compose exec backend python -m app.ml.benchmark` for model latency.

## 9. Upgrades

```bash
git pull
docker compose up -d --build     # migrations run on backend start
docker compose exec backend python -m app.db.seed   # adds new default settings; safe to re-run
```

After a model update also run `python -m app.db.recompute_references` (trainer references; `docs/MODEL_INTEGRATION.md` §7).

## 10. Limits of this setup

- **One backend instance.** Live events (WebSocket fan-out) and the analysis job queue are in-process. Running several backend replicas needs a shared bus and queue (e.g. Redis) behind the existing `EventBus`/`JobQueue` interfaces.
- The backend restarts cleanly (`restart: unless-stopped`): browsers reconnect their WebSockets and capture resumes without signing in again; interrupted analysis jobs are resumed.
- Accounts: if every admin is locked out, `docker compose exec backend python -m app.db.seed --reset-passwords` resets the demo accounts (including `admin`) to a new printed password.
