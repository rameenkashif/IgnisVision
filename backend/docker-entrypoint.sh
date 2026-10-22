#!/bin/sh
# Apply migrations, then start the API. Seed separately: python -m app.db.seed
set -e
alembic upgrade head
exec "$@"
