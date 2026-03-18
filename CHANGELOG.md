# Changelog

All notable changes to stockmgr are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.2.5] - 2026-03-18

### Added
- **Server-side PDF export on all list tables (#117)**: replaced the browser-print button with a **PDF** button on every `data-enhanced-table` table. Clicking it sends the currently-filtered, sorted rows to the new `POST /api/pdf/table` endpoint which generates an A4 PDF using `fpdf2` and pushes it as a download. The PDF includes:
  - A one-line filter summary (active search and column filters, shown on every page)
  - Column headers repeated on every page via `FPDF.header()`
  - Alternating row shading for readability
  - Page number and generation timestamp in the footer
  - Auto-selection of portrait (≤6 columns) or landscape (>6 columns) orientation
- **`POST /api/pdf/table` API endpoint**: session-authenticated JSON endpoint accepting `{title, filters, columns, rows}`, returning `application/pdf` with `Content-Disposition: attachment`. No CSRF required (read-only, session auth sufficient).
- **`fpdf2`** added to `requirements.txt`.

### Changed
- `table-enhance.js`: column label text is now stamped as `data-col-label` on each `<th>` before sort buttons replace the text content — used both for PDF column headers and for filter summaries.
- `beforeprint`/`afterprint` handlers retained so Ctrl+P / browser print still expands all filtered rows correctly.

## [1.2.4] - 2026-03-17

### Added
- **Print to PDF on all list tables**: every table enhanced by `table-enhance.js` now has a **Print** button in its controls bar. Clicking it (or using Ctrl+P / browser print) automatically expands the table to show **all currently-filtered rows** (bypassing pagination) before opening the print dialog, then restores the paginated view after. CSS `@media print` rules in `site.css` hide the navbar, table controls, pagination, and column-filter inputs; set `thead { display: table-header-group }` so headers repeat on every printed page; and format the table for A4 at 10pt. Covered tables: inventory list, renewal plan, shopping list, stock views (3 tables), food wheel plan, location plans, unidose plan, and admin users.
- **Global `@media print` CSS** in `site.css` replaces the per-template inline print style blocks that were previously duplicated in `renewals.html` and `unidose_plan.html`.

## [1.2.3] - 2026-03-17

### Fixed
- **Mixed content blocking all static assets (#103, #95)**: `url_for('static', path=...)` in Jinja2 was generating absolute `http://` URLs. Because the app runs behind Azure's HTTPS reverse proxy without `ProxyHeadersMiddleware`, FastAPI saw every request as HTTP and built HTTP static-file URLs. Browsers block `http://` scripts and stylesheets loaded from an `https://` page as mixed content — silently, in the background. This prevented `table-enhance.js` (and `site.css`) from ever loading, which is why column sorting never worked regardless of the JavaScript fixes applied in v1.2.1 and v1.2.2.
  - **Fix**: replaced all `url_for('static', path='...')` calls in `base.html` and `device_check.html` with root-relative `/static/...` paths. A root-relative path inherits the page scheme, so it is always `https://` in production and works correctly in local HTTP development too.

## [1.2.2] - 2026-03-17

### Fixed
- **Table column sorting still non-functional (#95)**: root-cause diagnosis revealed two issues: (1) browser was serving a stale cached `table-enhance.js` because the URL lacked a cache-busting parameter; (2) the dynamic `<style>` injection at script start was throwing before any tables were enhanced. Fixes:
  - Sort styles moved to `site.css` (always loaded, no runtime injection)
  - `site.css`, `table-enhance.js`, and `pwa-register.js` URLs now include `?v={{ app_version_semantic }}` for automatic cache-busting on every release
  - Controls and pagination now inserted outside `.table-responsive` wrapper (avoids clipping by overflow container)
  - Sort click handling switched to a single delegated listener on `<thead>` using `data-sort-col` stamps — more robust than per-button handlers
  - Each table's forEach wrapped in `try/catch` so one failing table can't prevent others from being enhanced

## [1.2.1] - 2026-03-17

### Fixed
- **Table column sorting non-functional (#95)**: sort click handlers were registered on `<th>` elements but produced no response in many browsers due to event-capture interference and lack of visible affordance. Fixed by replacing each sortable header's text with an explicit `<button class="sort-btn btn btn-link">` element — guarantees a reliable, browser-native click target.
- **Sort header hover feedback**: column headers now highlight with a light primary tint on hover, giving users a clear visual cue that headers are interactive.

## [1.2.0] - 2026-03-17

### Changed
- **Food wheel layout** (#97): chart (doughnut + stats) now renders above the location plan tabs
- **Sorting on all lists** (#95): added `data-enhanced-table` to unidose-plan table and food-wheel stats/plan-items tables; all lists now support column sorting and filtering via table-enhance.js
- **Item list enhancements** (#96):
  - Every item name is now a link to its product detail page across all list views (renewals, shopping list, unidose plan; was already present on homepage and stock views)
  - Hover over any item name → Bootstrap popover shows product image (if available) and name
  - Nutriscore badges now show a tooltip with full label on hover (e.g. "Nutri-score A")
  - New food group icon (12 px coloured circle) next to each item — hover shows group name
  - Food group data injected globally via `_render()` (`food_groups_map`); shopping list rows enriched with `image_url`
  - Overall and validity stock-view queries extended with `food_group` column



### Fixed
- **Item edit "Save changes" does nothing (#93)**: nested `<form>` (image upload) inside the main form caused the browser to implicitly close the outer form at its `</form>` tag, leaving the Save button outside any form. Fixed by replacing the inner form with a `<div>` and adding `formaction`/`formmethod`/`formenctype` attributes directly on the Upload button so it submits to the correct endpoint while remaining part of the outer form.

### Changed
- **Save button dirty-check**: in edit mode the Save button is now disabled by default and only enabled once any form field value has changed, preventing accidental saves.
- **Cancel button in edit mode**: now links back to the product detail page instead of home.



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
