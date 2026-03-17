# Copilot Instructions for `stockmgr`

Use this repository to build and maintain a SHTF stock inventory management system consisting of:
- A **web application** (FastAPI + SQLite + Jinja2) deployed on Azure App Service — primary source of truth
- A **React Native mobile app** (Expo, TypeScript) in `mobile/` — in planning, MVP scope defined in GitHub issues #106–#115

## Primary source of truth
- Product requirements baseline: `.github/project-requirements.md`
- Provider configuration schema: `config/barcode-providers.schema.json`
- Default provider configuration: `config/barcode-providers.default.json`
- Keep this requirements file up to date as decisions are refined.

## Repo structure
- `app/` — FastAPI web application (backend + Jinja2 UI)
- `mobile/` — React Native + Expo mobile app (to be created, see GitHub milestone "Mobile MVP v0.1")
- `config/` — barcode provider configuration
- `tests/` — pytest tests for the web app
- `.github/workflows/` — CI (`ci.yml`), deployment (`deploy.yml`), device smoke tests (`device-smoke.yml`)

## Implementation priorities — web app
1. Keep the web app stable; bump version on every change (`app/version.py` + `pyproject.toml`).
2. Surface errors explicitly; do not silently swallow failures.
3. Preserve existing behaviour when adding features; avoid breaking changes.
4. Treat provider integrations (calendar and barcode lookup) as configurable.
5. Keep code clear, testable, and easy to extend.

## Implementation priorities — mobile app
1. Scaffold Expo project in `mobile/` before any feature work (issue #108).
2. Backend API extensions (issues #106, #107) are prerequisites for most mobile screens.
3. Follow the dependency order defined in the milestone: infra → auth → inventory → detail → scanner → form.
4. All mobile code must be TypeScript strict mode; no `any` types.
5. Add a `mobile-ci.yml` workflow for TypeScript type checks.

## Constraints and expectations — both platforms
- Preserve existing web behaviour when adding mobile API endpoints.
- All new `/api/` endpoints must use `_require_api_user` (session cookie auth).
- Static asset URLs must use root-relative paths (`/static/...`) — never `url_for('static', ...)` — to avoid mixed-content blocking on HTTPS.
- Every code change to the web app must bump `pyproject.toml version` AND `app/version.py APP_VERSION`, update `CHANGELOG.md`, and update the version badge in `README.md`.
- Squash-merge PRs with commit title `"description (#PR_NUMBER)"` and `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` trailer.

