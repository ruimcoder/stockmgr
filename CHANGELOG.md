# Changelog

All notable changes to stockmgr are documented here. Versions follow [Semantic Versioning](https://semver.org/).

## [1.4.6] - 2026-04-22
### Added
- Configurable items-per-page dropdown with options [10, 25, 50, 100, 250] in all enhanced tables (#156)
- "Per page:" label added to the page-size control via Bootstrap input-group (#156)
- Page size selection persists across page loads via `localStorage` (key `table-page-size`) (#156)
- Pagination info now shows total filtered record count, e.g. "Page 2 / 5 (42 records)" (#156)

## [1.4.7] - 2026-04-21
### Added
- `qty_period` field on `BenchmarkItem` (day/week/month/fixed) to specify the time basis of the benchmark quantity (#157)
- DB migration: ALTER TABLE benchmarkitem ADD COLUMN qty_period for existing databases
- `_effective_daily_qty()` helper normalises qty to daily equivalent (week/7, month/30, fixed=absolute)
- `fixed` items bypass participant and duration scaling in gap analysis
- Period column and select in benchmark admin table + Add/Edit modals
- Inactive benchmark rows rendered with `table-row-inactive` CSS class (opacity 0.45)
- i18n keys: benchmark.qty_period, benchmark.period_day/week/month/fixed (EN + PT)
- Seed data: seeds, tools and communication items default to qty_period=fixed

## [1.4.4] - 2026-04-21
### Security
- Fixed path traversal vulnerability in restore_backup(): filename is now stripped of directory components and validated to remain inside the backup directory (CWE-22)
## [1.4.3] - 2026-04-21
### Changed
- GET /api/gap-analysis now returns a structured envelope with location metadata, summary counts, and enriched items (scales_with_participants, qty_per_day, target_stock) (#136)
### Fixed
- GET /api/gap-analysis returns 400 when location param is missing (previously raised unhandled validation error)
## [1.4.2] - 2026-04-22
### Added
- Shopping list now includes non-food items with unmet `target_unidoses_location` (#132)
- `item_category` and `non_food_category` added to shopping list query grouping (#132)
- Category badge (medicine, energy, tools, hygiene, seeds, communication, security) shown for non-food items in shopping list (#132)
- `data-category` attribute on shopping list `<tr>` rows for client-side filtering (#132)
- Client-side category filter (All / Food / Non-food) on shopping list page (#132)
- `data-category` attribute on renewals `<tr>` rows (#133)
- Category badge for non-food items in renewals list (#133)
- Client-side category filter on renewals page (#133)
- i18n keys: `shopping.non_food_section`, `shopping.food_section`, `shopping.category`, `renewals.category_filter` (EN + PT)

## [1.4.1] - 2026-04-22
### Added
- `data-category` and `data-nfc` attributes on inventory list `<tr>` rows (#131)
- Client-side category filter select in inventory list filter form (#131)
- `filterByCategory()` inline JS function for client-side row filtering (#131)
- CSS badge classes for non-food sub-categories (`badge-medicine`, `badge-energy`, etc.) in `site.css` (#131)
- i18n keys: `filter.category`, `filter.food_only`, `filter.non_food_only` (EN + PT)

## [1.4.0] - 2026-04-21
### Added
- Stock Gap Analysis dashboard at `/gap-analysis` (#130)
- `compute_gap_rows()` in `app/gap_utils.py`: calculates per-benchmark-item coverage, gap, days covered and status ("ok"/"partial"/"missing") for a location
- GET `/gap-analysis` — authenticated page with location selector, summary cards and sortable coverage table
- GET `/api/gap-analysis?location=<loc>` — JSON API endpoint returning gap rows for mobile/external consumers
- `app/templates/gap_analysis.html`: Bootstrap table with progress bars, colour-coded rows and summary cards
- Nav link "Gap Analysis" added to main navbar
- i18n keys: `gap.*`, `nav.gap_analysis` (EN + PT)
- Tests in `tests/test_gap_analysis.py` covering coverage calculation, disabled exclusion, missing stock, sort order, page render

## [1.3.9] - 2026-04-21
### Added
- Per-location benchmark configuration UI at `/location-plans/{location}/benchmark` (#129)
- GET `/location-plans/{location}/benchmark` — view and configure benchmark items for a location
- PATCH `/api/location-benchmark/{lb_id}/toggle` — toggle `is_enabled` for a benchmark row
- PATCH `/api/location-benchmark/{lb_id}/override` — set or clear `qty_override` for a benchmark row
- POST `/api/location-benchmark/{location}/reset-all` — reset all overrides and re-enable all items for a location
- "Configure Benchmark" button in `location_plans.html` table actions column
- i18n keys: `location_benchmark.*`, `benchmark.no_items`, `common.all` (EN + PT)
- Tests in `tests/test_location_benchmark_ui.py` covering 404, render, toggle, override set/clear

## [1.3.8] - 2026-04-21
### Added
- `LocationBenchmark` SQLModel table for per-location benchmark overrides (#128)
- `sync_location_benchmarks()` in `app/benchmark_seed.py`: ensures every active `BenchmarkItem` has a `LocationBenchmark` row for every `LocationPlan` location; called at startup via lifespan (#128)
- `app/gap_utils.py`: `get_target_qty()` helper — calculates target stock quantity respecting per-location overrides, enable/disable flag, and participant scaling (#128)
- Tests in `tests/test_location_benchmark.py` covering scaling, overrides, disabled items, sync creation and idempotency (#128)

## [1.3.7] - 2026-04-21
### Added
- Benchmark management UI at `/benchmark` (admin only) (#127)
- GET/POST `/benchmark` — list and create benchmark items with Bootstrap modal form
- POST `/benchmark/{id}/update` — AJAX update item fields (JSON)
- DELETE `/benchmark/{id}` — AJAX delete item
- POST `/benchmark/{id}/toggle` — AJAX toggle `is_active`
- `app/templates/benchmark.html`: table with `data-enhanced-table`, edit/delete/toggle actions
- Benchmark tab in `/admin/config` settings page linking to `/benchmark`
- i18n keys: `settings.benchmark.*`, `benchmark.add_item`, `benchmark.edit`, `benchmark.delete`, `benchmark.confirm_delete`, `benchmark.scales_yes`, `benchmark.scales_no`, `benchmark.inactive`, `benchmark.name_en`, `benchmark.name_pt`, `benchmark.sort_order`, `benchmark.is_active` (EN + PT)

## [1.3.6] - 2026-04-21
### Added
- `BenchmarkItem` SQLModel table with curated prepper seed data (35 items across food, medicine, hygiene, energy, seeds, tools, communication) (#126)
- `app/benchmark_seed.py`: idempotent `seed_benchmark_if_empty()` called at startup via lifespan (#126)
- i18n keys: `benchmark.title`, `benchmark.category`, `benchmark.qty_per_day`, `benchmark.scales`, `benchmark.notes`, `benchmark.name`, `benchmark.uom` (EN + PT) (#126)

## [1.3.5] - 2026-04-21
### Added
- Item form: `item_category` radio (Food/Non-food) and `non_food_category` select, shown prominently after barcode section (#125)
- Category-aware field visibility: food-only fields (nutriscore, food group) hidden for non-food items; non-food category shown only for non-food items (#125)
- `app/static/item_form.js`: `updateCategoryVisibility()` and `updateExpiryRequired()` functions with DOM-load binding (#125)
- Inventory list: category emoji badge next to each item name (🌿 food, 💊 medicine, ⛽ energy, 🔧 tools, 🧼 hygiene, 🌱 seeds, 📻 communication, 🛡️ security, 📦 other) (#125)
- i18n keys: `form.item_category`, `form.non_food_category`, `form.select_category`, `badge.*` (EN + PT) (#125)

## [1.3.4] - 2026-04-21
### Changed
- UOM field is now a standardized dropdown (L, mL, kg, g, unit, pack, dose, roll, m2, kWh) (#124)
### Added
- app/uom_constants.py: UOM_OPTIONS (10 units with EN/PT labels) and normalize_uom() alias helper
- Excel/CSV import UOM normalization (common aliases mapped to standard keys)
- i18n keys: form.uom, form.uom_placeholder, uom.* (EN + PT)

## [1.3.3] - 2026-04-21
### Changed
- expiry_date is now optional for non-food items (except medicine, seeds, energy) (#123)
### Added
- Server-side validation: expiry_date required for food, medicine, seeds, energy items
- GET /api/items accepts `?category=` and `?non_food_category=` query params (#135)
- `item_category` and `non_food_category` in all `ItemRead` API responses (#135)
- i18n keys: form.expiry_optional_hint (EN + PT)
### Fixed
- Food wheel calculations now exclude non-food items (item_category=non_food) (#134)
- Backward compatible: items without item_category (legacy/NULL) still included as food (#134)

## [1.2.9] - 2026-04-20
### Added
- item_category field on StockItem: "food" (default) | "non_food" (#122)
- non_food_category field on StockItem: medicine/energy/tools/hygiene/seeds/communication/security/other (#122)
- app/non_food_categories.py: category constants with EN/PT translations
- i18n keys: category.food, category.non_food, nfc.* (EN + PT)

## [1.2.8] - 2026-04-20
### Added
- Database backup and restore mechanism: automatic backup on startup, admin API endpoints, Settings UI panel (#121)
- `scripts/backup_db.py` standalone backup CLI

## [1.2.7] - 2026-03-18

### Changed
- **Telegram integration moved out of FastAPI into a standalone CLI bridge**:
  - Added `scripts/telegram_copilot_bridge.py` for Telegram <-> Copilot CLI conversations via long polling.
  - Bridge keeps per-chat short history for fluent back-and-forth, supports `/help` and `/reset`, and can restrict access with `TELEGRAM_ALLOWED_USER_ID` and `TELEGRAM_ALLOWED_CHAT_ID`.
  - App endpoint `POST /api/telegram/webhook` is now deprecated and returns `410 Gone` with migration guidance.
  - App-level Telegram operation notifications are disabled; Telegram interaction is now handled by the standalone bridge process.

### Tests
- Replaced app-webhook Telegram tests with coverage for the new deprecated endpoint behavior and stock-move stability without app-level Telegram wiring.

## [1.2.6] - 2026-03-18

### Changed
- **Telegram command handling is now fluent for two-way bot chats**:
  - Supports Telegram command mentions such as `/health@your_bot` (common in group and forwarded command contexts).
  - Supports natural-language aliases without slash commands (`inventory`, `health`, `moves 10`, `find rice`).
  - Treats unmatched free text as product search input (e.g., sending `rice` runs the equivalent of `/find rice`).
  - Help output now documents free-text usage examples.

### Tests
- Added coverage for command-mention parsing and free-text Telegram query handling in `tests/test_telegram.py`.

## [1.2.5] - 2026-03-18

### Added
- **Server-side PDF export on all list tables (#117)**: replaced the browser-print button with a **PDF** button on every `data-enhanced-table` table. Clicking it sends the currently-filtered, sorted rows to the new `POST /api/pdf/table` endpoint which generates an A4 PDF using `fpdf2` and pushes it as a download. The PDF includes:
  - A one-line filter summary (active search and column filters, shown on every page)
  - Column headers repeated on every page via `FPDF.header()`
  - Alternating row shading for readability
  - Page number and generation timestamp in the footer
  - Auto-selection of portrait (Γëñ6 columns) or landscape (>6 columns) orientation
- **`POST /api/pdf/table` API endpoint**: session-authenticated JSON endpoint accepting `{title, filters, columns, rows}`, returning `application/pdf` with `Content-Disposition: attachment`. No CSRF required (read-only, session auth sufficient).
- **`fpdf2`** added to `requirements.txt`.

### Changed
- `table-enhance.js`: column label text is now stamped as `data-col-label` on each `<th>` before sort buttons replace the text content ΓÇö used both for PDF column headers and for filter summaries.
- `beforeprint`/`afterprint` handlers retained so Ctrl+P / browser print still expands all filtered rows correctly.

## [1.2.4] - 2026-03-17

### Added
- **Print to PDF on all list tables**: every table enhanced by `table-enhance.js` now has a **Print** button in its controls bar. Clicking it (or using Ctrl+P / browser print) automatically expands the table to show **all currently-filtered rows** (bypassing pagination) before opening the print dialog, then restores the paginated view after. CSS `@media print` rules in `site.css` hide the navbar, table controls, pagination, and column-filter inputs; set `thead { display: table-header-group }` so headers repeat on every printed page; and format the table for A4 at 10pt. Covered tables: inventory list, renewal plan, shopping list, stock views (3 tables), food wheel plan, location plans, unidose plan, and admin users.
- **Global `@media print` CSS** in `site.css` replaces the per-template inline print style blocks that were previously duplicated in `renewals.html` and `unidose_plan.html`.

## [1.2.3] - 2026-03-17

### Fixed
- **Mixed content blocking all static assets (#103, #95)**: `url_for('static', path=...)` in Jinja2 was generating absolute `http://` URLs. Because the app runs behind Azure's HTTPS reverse proxy without `ProxyHeadersMiddleware`, FastAPI saw every request as HTTP and built HTTP static-file URLs. Browsers block `http://` scripts and stylesheets loaded from an `https://` page as mixed content ΓÇö silently, in the background. This prevented `table-enhance.js` (and `site.css`) from ever loading, which is why column sorting never worked regardless of the JavaScript fixes applied in v1.2.1 and v1.2.2.
  - **Fix**: replaced all `url_for('static', path='...')` calls in `base.html` and `device_check.html` with root-relative `/static/...` paths. A root-relative path inherits the page scheme, so it is always `https://` in production and works correctly in local HTTP development too.

## [1.2.2] - 2026-03-17

### Fixed
- **Table column sorting still non-functional (#95)**: root-cause diagnosis revealed two issues: (1) browser was serving a stale cached `table-enhance.js` because the URL lacked a cache-busting parameter; (2) the dynamic `<style>` injection at script start was throwing before any tables were enhanced. Fixes:
  - Sort styles moved to `site.css` (always loaded, no runtime injection)
  - `site.css`, `table-enhance.js`, and `pwa-register.js` URLs now include `?v={{ app_version_semantic }}` for automatic cache-busting on every release
  - Controls and pagination now inserted outside `.table-responsive` wrapper (avoids clipping by overflow container)
  - Sort click handling switched to a single delegated listener on `<thead>` using `data-sort-col` stamps ΓÇö more robust than per-button handlers
  - Each table's forEach wrapped in `try/catch` so one failing table can't prevent others from being enhanced

## [1.2.1] - 2026-03-17

### Fixed
- **Table column sorting non-functional (#95)**: sort click handlers were registered on `<th>` elements but produced no response in many browsers due to event-capture interference and lack of visible affordance. Fixed by replacing each sortable header's text with an explicit `<button class="sort-btn btn btn-link">` element ΓÇö guarantees a reliable, browser-native click target.
- **Sort header hover feedback**: column headers now highlight with a light primary tint on hover, giving users a clear visual cue that headers are interactive.

## [1.2.0] - 2026-03-17

### Changed
- **Food wheel layout** (#97): chart (doughnut + stats) now renders above the location plan tabs
- **Sorting on all lists** (#95): added `data-enhanced-table` to unidose-plan table and food-wheel stats/plan-items tables; all lists now support column sorting and filtering via table-enhance.js
- **Item list enhancements** (#96):
  - Every item name is now a link to its product detail page across all list views (renewals, shopping list, unidose plan; was already present on homepage and stock views)
  - Hover over any item name ΓåÆ Bootstrap popover shows product image (if available) and name
  - Nutriscore badges now show a tooltip with full label on hover (e.g. "Nutri-score A")
  - New food group icon (12 px coloured circle) next to each item ΓÇö hover shows group name
  - Food group data injected globally via `_render()` (`food_groups_map`); shopping list rows enriched with `image_url`
  - Overall and validity stock-view queries extended with `food_group` column



### Fixed
- **Item edit "Save changes" does nothing (#93)**: nested `<form>` (image upload) inside the main form caused the browser to implicitly close the outer form at its `</form>` tag, leaving the Save button outside any form. Fixed by replacing the inner form with a `<div>` and adding `formaction`/`formmethod`/`formenctype` attributes directly on the Upload button so it submits to the correct endpoint while remaining part of the outer form.

### Changed
- **Save button dirty-check**: in edit mode the Save button is now disabled by default and only enabled once any form field value has changed, preventing accidental saves.
- **Cancel button in edit mode**: now links back to the product detail page instead of home.



### Fixed
- **Food wheel 500 (regression)**: `plan_tabs` was passing live SQLAlchemy ORM objects to Jinja2; after the session closes, Starlette renders the template and attribute access on expired instances raises `DetachedInstanceError`. Fixed by converting `LocationPlan` and `StockItem` entries to plain dicts before returning from the route. Also renamed dict key `items` ΓåÆ `plan_items` to avoid collision with Python's built-in `dict.items` method, which Jinja2 resolves as a callable instead of the dict value.

## [1.1.1] - 2026-03-16

### Fixed
- **Product detail 500**: `LocationPlan.days` does not exist ΓÇö corrected to `stock_duration_days` (#87)
- **Food wheel 500 on mobile**: wrapped full route body in try/except with structured logging; inner chart errors also now isolated (#88)
- **Unidose plan print**: added A4 print/PDF button with repeating table headers (#89)

### Changed
- Merged authlib security update 1.6.7 ΓåÆ 1.6.9 (#90)

## [1.1.0] - 2026-03-16

### Added
- **Versioning system**: semantic version `1.1.0` in `pyproject.toml` and `app/version.py`; version badge shown in navbar
- **`/admin/info` page**: shows semantic version, build date, deploy SHA, database size and row counts (#84)
- **Renewal plan overhaul**: now shows items expiring in the next configurable window; added location filter and browser print/PDF button (#83)
- **Enrich page progress**: real-time per-item SSE progress stream with status log (#81)
- **JSON validation in config page**: client-side validation with error position before saving provider config (#82)

### Fixed
- **`GET /items/unidose-plan`**: route decorator was missing ΓÇö page now loads correctly (#79)
- **Food wheel 500 error**: added error guard around chart data computation (#80)
- **Column sort indicators**: Γåæ/Γåô/Γçà icons on all sortable table columns in all stock views (#78)

## [1.0.0] - 2026-02-20

### Added
- **AJAX barcode lookup**: converts barcode search to fetch-based flow ΓÇö no page refresh; provider badges show attempt results
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
- CSRF token suppressed by overlay `disabled` attribute ΓÇö fixed by removing input disable logic

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


