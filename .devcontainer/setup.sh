#!/usr/bin/env bash
# Runs once when the codespace is created: writes .env with random secrets and the
# codespace's public address. Safe to re-run; an existing .env is kept.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env already exists; leaving it unchanged."
  exit 0
fi

rand() { head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
origin="https://${CODESPACE_NAME:-localhost}-8080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
[ -z "${CODESPACE_NAME:-}" ] && origin="http://localhost:8080"

cp .env.example .env
sed -i \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand 32)|" \
  -e "s|^JWT_SECRET=.*|JWT_SECRET=$(rand 48)|" \
  -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=[\"${origin}\"]|" \
  -e "s|^MOCK_SCENARIO=.*|MOCK_SCENARIO=escalating|" \
  .env
# Demo accounts' password (letters and digits, so it passes the password rules).
echo "SEED_PASSWORD=Demo-$(rand 10)-1" >> .env
echo "Wrote .env for ${origin}"
