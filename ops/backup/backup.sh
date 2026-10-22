#!/bin/sh
# Daily pg_dump with rotation (SRS §5.2.2). Restore:
#   docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists < backups/<file>.dump
set -eu
while true; do
  ts=$(date -u +%Y%m%dT%H%M%SZ)
  if pg_dump -Fc -f "/backups/ignis-$ts.dump.tmp"; then
    mv "/backups/ignis-$ts.dump.tmp" "/backups/ignis-$ts.dump"
    date -u +%Y-%m-%dT%H:%M:%SZ > /backups/LAST_BACKUP
    echo "backup ok: ignis-$ts.dump"
  else
    rm -f "/backups/ignis-$ts.dump.tmp"
    echo "backup FAILED at $ts" >&2
  fi
  find /backups -name 'ignis-*.dump' -mtime +"${BACKUP_RETENTION_DAYS:-7}" -delete
  sleep 86400
done
