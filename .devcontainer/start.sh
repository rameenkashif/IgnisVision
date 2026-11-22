#!/usr/bin/env bash
# Runs every time the codespace starts: builds and starts the stack, seeds the demo data,
# and prints the address and demo password. Run it again by hand at any time.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || bash .devcontainer/setup.sh

for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done

docker compose -f docker-compose.yml -f docker-compose.codespaces.yml up -d --build

echo "Waiting for the backend…"
for _ in $(seq 1 90); do
  curl -sf http://localhost:8080/api/v1/health/ready >/dev/null && break
  sleep 2
done
docker compose exec -T backend python -m app.db.seed >/dev/null

password=$(grep '^SEED_PASSWORD=' .env | cut -d= -f2-)
if [ -n "${CODESPACE_NAME:-}" ]; then
  url="https://${CODESPACE_NAME}-8080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
else
  url="http://localhost:8080"
fi
cat <<MSG

  Ignis Vision is running:  ${url}
  Accounts: admin, commander1, responder1, trainee1, trainer1
  Password: ${password}

  (Also in .env as SEED_PASSWORD. Docs: docs/DEMO.md)

MSG
