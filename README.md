# stockmgr

Web MVP to manage SHTF stock inventory with OAuth-capable authentication, barcode-assisted item entry, CSV/XLSX import, renewal-date calendar sync, and configurable product-information providers.

## MVP capabilities
- OAuth-capable auth (Google/Microsoft) plus local development login mode.
- Mandatory fields: type, name, storage location, expiry date.
- Inventory fields: item name/type, location, bucket (optional), batch code (optional), expiry date, temperature range, humidity range, renewal date, barcode.
- Supports multiple batches of the same product (same product/barcode with different batch codes and expiry dates).
- Supports stock quantity per batch, including increment/decrement operations with optional notes and movement logs.
- Product detail page now includes a product summary section and an edit shortcut that opens the existing item edit page with the same product's batches and movement log context.
- Product detail page includes quick actions to add a new storage location for a product, or add a new batch for an existing product/location with prefilled item creation form data.
- Supports unidose planning fields (`unidose_per_pack`, `target_unidoses_location`) and automatic unidoses delta calculations per location.
- Barcode lookup endpoint backed by provider-priority config (Portugal-first defaults).
- User-friendly web UI for manual entry, barcode-assisted entry, camera barcode scanning with automatic search submit, compatibility fallback mode for unsupported browsers, datagrid listing/editing, and file import.
- Mobile-first responsive UI with installable PWA support (Android and iOS home-screen mode).
- Refreshed multi-size app icon set (favicon, Apple touch icon, Android/PWA icons, maskable icon) for consistent recognition across devices.
- In-app device diagnostics page (`/device-check`) to validate camera/PWA/browser capabilities on each device.
- Multilanguage UI switcher (Portuguese and English).
- Stock views include: per product overall, per product and storage location, and per product/location/expiry.
- Stock list supports filtering by bucket assignment (assigned/unassigned) and storage location.
- Shopping list computes quantity-to-buy totals and per-location distribution.
- Homepage quick search: find by name or barcode, opening product detail when in stock or prefilled new-item form when not in stock.
- Excel integration API for read/write stock editing (`/api/excel/stocks`, `/api/excel/stocks/{id}`, `/api/excel/stocks/upsert`) with API-key authentication.
- All list tables support paging, column filtering, and column ordering.
- Renewal plan includes configurable time window (`RENEWAL_WINDOW_DAYS` default, overrideable in UI).
- Users can register; account access requires admin approval. Admins can approve/reject users and toggle admin role.
- Calendar sync service abstraction for Google or Microsoft provider modes.
- Automated tests and GitHub Actions for CI + image deployment.

## Project structure
- App code: `app/`
- Provider config schema: `config/barcode-providers.schema.json`
- Default provider config: `config/barcode-providers.default.json`
- CI workflow: `.github/workflows/ci.yml`
- Deploy workflow: `.github/workflows/deploy.yml`

## Local setup
1. Create and activate a virtual environment.
2. Install dependencies.
3. Run the app.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Open: `http://127.0.0.1:8000`

> Camera scanning works on `localhost` and HTTPS deployments. Browsers require explicit camera permission approval.

## Mobile / PWA usage
- Install prompt is available in compatible browsers after opening the app over HTTPS.
- Android: Chrome supports install and camera scanning in-browser/PWA mode.
- iPhone: use Safari "Add to Home Screen" for standalone mode; camera access still requires permission.

## Local test run
```powershell
.\.venv\Scripts\Activate.ps1
ruff check .
pytest
```

## Runtime configuration
Create a `.env` file (optional) to override defaults:

```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///./stockmgr.db
SECRET_KEY=replace-this
AUTH_MODE=dev
CALENDAR_PROVIDER=none
RENEWAL_WINDOW_DAYS=30
ADMIN_EMAILS=admin@example.com

# Optional OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# Optional provider keys
USDA_API_KEY=
OPENFDA_API_KEY=
UPCITEMDB_API_KEY=
GO_UPC_API_KEY=
GS1_US_API_KEY=

# Optional Excel API access
EXCEL_API_KEY=
EXCEL_API_USER_EMAIL=
```

## Excel datasource API (read + write)
- Authentication: set `X-Excel-Api-Key` header (or `X-API-Key`) to `EXCEL_API_KEY`.
- User scope: by default uses `EXCEL_API_USER_EMAIL`; can override per request with `X-Excel-User-Email`.
- Endpoints:
  - `GET /api/excel/stocks` → list stock rows (read datasource).
  - `PUT /api/excel/stocks/{id}` → update a row.
  - `POST /api/excel/stocks/upsert` → batch create/update rows from worksheet data.

## Build and deploy
- **CI** (`ci.yml`): lint + tests + Docker build on push/PR.
- **Deploy to Azure** (`deploy.yml`): validates Azure infra, builds/pushes image to GHCR, deploys container to Azure Web App, then runs smoke tests.
- **Device smoke** (`device-smoke.yml`): Playwright smoke tests across Firefox desktop, Android Chrome emulation, and iPhone Safari emulation.

## Azure deployment pipeline setup
1. Provision Azure Linux Web App infrastructure (resource group, App Service plan, Web App).
2. Configure GitHub repository **Variables**:
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_APPSERVICE_PLAN`
   - `AZURE_WEBAPP_NAME`
   - Optional: `AZURE_APPSERVICE_PLAN_RESOURCE_GROUP`, `AUTH_MODE`, `CALENDAR_PROVIDER`, `RENEWAL_WINDOW_DAYS`, `ADMIN_EMAILS`, `EXCEL_API_USER_EMAIL`
3. Configure GitHub repository **Secrets**:
   - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (OIDC service principal)
   - `GHCR_USERNAME`, `GHCR_TOKEN` (token must allow package read for Azure pull)
   - Recommended: `SECRET_KEY`, optional `EXCEL_API_KEY`
4. The workflow runs infra validation first using `scripts/azure/validate_infra.sh`, deploys the container, and then validates runtime with `scripts/azure/smoke_test.sh`.

### Local script dry-run (optional)
```powershell
az login
$env:AZURE_RESOURCE_GROUP="rg-stockmgr"
$env:AZURE_APPSERVICE_PLAN="asp-stockmgr"
$env:AZURE_WEBAPP_NAME="stockmgr-prod"
bash scripts/azure/validate_infra.sh
$env:AZURE_WEBAPP_URL="https://stockmgr-prod.azurewebsites.net"
bash scripts/azure/smoke_test.sh
```

## Cross-device validation (local)
```powershell
uvicorn app.main:app --reload
npx --yes playwright@1.54.2 install chromium firefox webkit
npx --yes playwright@1.54.2 test -c playwright.config.js
```

## Agent and requirements docs
- Copilot instructions: `.github/copilot-instructions.md`
- Requirements baseline: `.github/project-requirements.md`
