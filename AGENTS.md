# Repository Guidelines

## Project Structure & Module Organization
- Django project root uses `manage.py` with settings in `CRAproject/`; add new apps there.
- Core apps cover authentication and hazard workflows: `accounts`, `overrides`, `posts`, and analysis modules (`climate_hazards_analysis`, `climate_hazards_analysis_v2`, `flood_exposure_analysis`, `heat_exposure_analysis`, `sea_level_rise_analysis`, `tropical_cyclone_analysis`, `water_stress`).
- Shared templates live in `templates/` plus app-level templates; static assets in `static/` and collected output in `staticfiles/`.
- Docs and troubleshooting notes sit in `docs/` and the root `*_SUMMARY.md` files; sample console/demo scripts and ad hoc tests are in the repo root (`demo_*`, `test_*`).
- `db.sqlite3` backs local development; swap to Postgres via env vars for shared deployments.

## Build, Test, and Development Commands
- Environment: `python -m venv .venv; .\.venv\Scripts\activate` then `pip install -r requirements.txt`.
- Database: `python manage.py migrate` (and `createsuperuser` when needed).
- Run locally: `python manage.py runserver 0.0.0.0:8000`.
- Static files: `python manage.py collectstatic --noinput` for production targets (served via WhiteNoise).
- Tests: `python manage.py test` for Django test modules; targeted workflow checks use scripts such as `python test_json_workflow.py` or `python test_complete_workflow.py` from the project root.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indents and `snake_case` functions; use `CamelCase` for models/services and uppercase module constants.
- Keep Django templates and static assets grouped by app; name templates descriptively (e.g., `hazard_selection.html`).
- Prefer explicit imports and small, single-responsibility helpers in `utils/`; add docstrings for non-obvious logic.

## Testing Guidelines
- Place new tests as `test_*.py` with `test_*` functions; mirror app structure when adding package-level tests.
- Favor assertions over print statements; cover both API views and utility paths (e.g., `granular_utils`, JSON upload handlers).
- When adding data-dependent tests, use lightweight fixtures and clean up any temp files.

## Commit & Pull Request Guidelines
- Use concise, conventional commit subjects when possible (e.g., `feat(override-colors): add threshold color coding`, `fix(json-upload): handle missing CRS`).
- PRs should describe user impact, list key commands run (`python manage.py test`, relevant `python test_*.py`), and link issues or tickets.
- Include before/after screenshots or sample JSON payloads when touching templates, assets, or API responses.

## Security & Configuration Tips
- Secrets and per-environment settings load from `CRAproject/.env`; do not commit credentials. Set `DEBUG=False` and tighten `ALLOWED_HOSTS` for non-local runs.
- Ensure `collectstatic` and database migrations are executed in CI/CD; avoid storing large datasets in the repo and prefer volume-mounted or S3 inputs.
