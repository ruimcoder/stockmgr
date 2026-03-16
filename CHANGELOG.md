# Changelog

All notable changes to stockmgr are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.1.2] - 2026-03-17

### Fixed
- **Food wheel 500 (regression)**: `plan_tabs` was passing live SQLAlchemy ORM objects to Jinja2; after the session closes, Starlette renders the template and attribute access on expired instances raises `DetachedInstanceError`. Fixed by converting `LocationPlan` and `StockItem` entries to plain dicts before returning from the route. Also renamed dict key `items` → `plan_items` to avoid collision with Python's built-in `dict.items` method, which Jinja2 resolves as a callable instead of the dict value.

## [1.1.1] - 2026-03-16

### Fixed
- **Product detail 500**: `LocationPlan.days` does not exist — corrected to `stock_duration_days` (#87)
- **Food wheel 500 on mobile**: wrapped full route body in try/except with structured logging; inner chart errors also now isolated (#88)
- **Unidose plan print**: added A4 print/PDF button with repeating table headers (#89)

### Changed
- Merged authlib security update 1.6.7 → 1.6.9 (#90)

## [1.1.0] - 2026-03-16

### Added
- **Versioning system**: semantic version `1.1.0` in `pyproject.toml` and `app/version.py`; version badge shown in navbar
- **`/admin/info` page**: shows semantic version, build date, deploy SHA, database size and row counts (#84)
- **Renewal plan overhaul**: now shows items expiring in the next configurable window; added location filter and browser print/PDF button (#83)
- **Enrich page progress**: real-time per-item SSE progress stream with status log (#81)
- **JSON validation in config page**: client-side validation with error position before saving provider config (#82)

### Fixed
- **`GET /items/unidose-plan`**: route decorator was missing — page now loads correctly (#79)
- **Food wheel 500 error**: added error guard around chart data computation (#80)
- **Column sort indicators**: ↑/↓/⇅ icons on all sortable table columns in all stock views (#78)

## [1.0.0] - 2026-02-20

### Added
- **AJAX barcode lookup**: converts barcode search to fetch-based flow — no page refresh; provider badges show attempt results
- **Barcode lookup progress overlay**: spinner with cycling provider names; stops when response arrives
- **Nutriscore UI**: editable select in forms, colour-coded badges in list views
- **Config admin page** (`/admin/config`): live editing of barcode provider JSON with `reload_config()`
- **Product image upload**: image upload via `/items/{id}/upload-image`
- **XLSX export** at `/items/export`
- **Backup/restore** admin pages (`/admin/backup`, `/admin/restore`)
- **Food wheel** chart (`/food-wheel`): Portuguese food wheel distribution vs recommended
- **Unidose plan** page (`/items/unidose-plan`): bulk edit of unidoses per day per person
- **Location plan modal** in item form for quick plan creation
- **Weight/capacity fields** (`weight_capacity`, `uom`) on stock items
- **`stopOnSuccess`** flag on Open Food Facts provider (stops lookup chain when first provider finds a match)
- **`/admin/enrich`** page for bulk barcode re-enrichment
- `OpenFoodFacts` given highest priority in default provider chain

### Fixed
- URL path separator bug when product names contain `/`
- Auto-submit barcode loop fixed with `lookupAlreadyDone` guard (superseded by AJAX approach)
- CSRF token suppressed by overlay `disabled` attribute — fixed by removing input disable logic

## [0.9.0] - 2026-01-15

### Added
- Initial MVP: OAuth auth (Google/Microsoft), SQLite storage, stock inventory management
- Barcode lookup with provider chain (Open Food Facts, Open Products Facts, USDA, openFDA, UPCitemdb, Go-UPC, Continente PT)
- Manual item entry, data-grid editing, Excel/CSV import
- Shopping list with quantity-to-buy calculation
- Renewal date calendar appointment integration
- Telegram operations channel with owner-only access control
- PWA support (installable, camera scanning)
- Portuguese/English multilanguage UI
- Excel API for external datasource read/write
- User registration with admin approval workflow
- Automated CI (lint + tests + Docker build) and Azure deployment pipeline
