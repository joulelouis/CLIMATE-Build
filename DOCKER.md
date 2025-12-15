# Docker usage

This image runs the Django app with Gunicorn and WhiteNoise. It installs GDAL/geo dependencies for raster/vector workflows.

## Build
```sh
docker build -t climate-build .
```

## Run (SQLite, development-friendly)
```sh
docker run -p 8000:8000 \
  -e DJANGO_DEBUG=True \
  -e DJANGO_SECRET_KEY=dev-secret-change-me \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  -v climate-db:/app/db.sqlite3 \
  --name climate-build \
  climate-build
```
- Migrations and `collectstatic` run automatically; set `SKIP_MIGRATIONS=1` or `SKIP_COLLECTSTATIC=1` to skip.
- The volume keeps the SQLite database outside the container image.

## Run with an env file
Place environment variables in `CRAproject/.env` (or another file) and pass it through:
```sh
docker run -p 8000:8000 --env-file CRAproject/.env climate-build
```

## Configuration notes
- Set `DJANGO_DEBUG=False` and provide your own `DJANGO_SECRET_KEY` for non-local environments.
- `DJANGO_ALLOWED_HOSTS` accepts a comma-separated list (e.g., `app.example.com,localhost`).
- The default database is SQLite. To switch to Postgres, update `CRAproject/settings.py` to use the Postgres configuration and supply DB-related env vars.
