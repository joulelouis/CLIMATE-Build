#!/bin/sh
set -e

# Run database migrations before starting the server.
if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
  python manage.py migrate --noinput
fi

# Collect static files for WhiteNoise unless explicitly skipped.
if [ "${SKIP_COLLECTSTATIC:-0}" != "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
