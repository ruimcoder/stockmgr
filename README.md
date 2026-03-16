# stockmgr

![Version](https://img.shields.io/badge/version-1.1.0-blue)

Web MVP to manage SHTF stock inventorywith OAuth-capable authentication, barcode-assisted item entry, CSV/XLSX import, renewal-date calendar sync, and configurable product-information providers.

## MVP capabilities
- OAuth-capable auth (Google/Microsoft) plus local development login mode.
- Mandatory fields: type, name, storage location, expiry date.
- Inventory fields: item name/type, location, bucket (optional), batch code (optional), expiry date, temperature range, humidity range, renewal date, barcode.
- Supports multiple batches of the same product (same product/barcode with different batch codes and expiry dates).
- Supports stock quantity per batch, including increment/decrement operations with optional notes and movement logs.
- Inventory data is shared across all approved users (not user-isolated), so authorized users work on the same stock records.
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
- Secure Telegram operations channel (`/api/telegram/webhook`) with strict sender validation (webhook secret + allowed user/chat IDs) and command-driven status/inventory outputs.
- All list tables support paging, column filtering, and column ordering.
- Renewal plan includes configurable time window (`RENEWAL_WINDOW_DAYS` default, overrideable in UI).
- Users can register; account access requires admin approval. Admins can approve/reject users and toggle admin role.
- Calendar sync service abstraction for Google or Microsoft provider modes.
- Automated tests and GitHub Actions for CI + image deployment.
- Renewal plan shows items expiring within a configurable window with location filter and browser print/PDF export.
- Real-time enrich progress: SSE-based per-item status stream during barcode re-enrichment.
- Barcode lookup is AJAX-based with no page refresh; provider attempt badges show per-provider results.
- Sort direction indicators (↑/↓/⇅) on all table columns; clicking header toggles ascending/descending.
- Configuration page validates JSON format before saving barcode provider config.
- Application info page (`/admin/info`) shows semantic version, build date, deploy SHA, and database stats.

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

# Optional Telegram operations channel
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_ALLOWED_USER_ID=
TELEGRAM_ALLOWED_CHAT_ID=
TELEGRAM_REQUIRE_PRIVATE_CHAT=true
```

Barcode provider behavior is driven by `config/barcode-providers.default.json`.
The `continente_pt` connector is implemented with barcode search + product-page scraping
and is active in the default lookup chain configuration.

## Excel datasource API (read + write)
- Authentication: set `X-Excel-Api-Key` header (or `X-API-Key`) to `EXCEL_API_KEY`.
- Request identity: by default uses `EXCEL_API_USER_EMAIL`; can override per request with `X-Excel-User-Email`.
- Endpoints:
  - `GET /api/excel/stocks` → list stock rows (read datasource).
  - `PUT /api/excel/stocks/{id}` → update a row.
  - `POST /api/excel/stocks/upsert` → batch create/update rows from worksheet data.

## Telegram operations channel
- Endpoint: `POST /api/telegram/webhook`
- Security gates:
  - `X-Telegram-Bot-Api-Secret-Token` header must match `TELEGRAM_WEBHOOK_SECRET`.
  - Sender `from.id` must match `TELEGRAM_ALLOWED_USER_ID`.
  - Chat `chat.id` must match `TELEGRAM_ALLOWED_CHAT_ID`.
  - Private chat can be enforced with `TELEGRAM_REQUIRE_PRIVATE_CHAT=true`.
- Supported commands: `/help`, `/health`, `/inventory`, `/find <name>`, `/moves [N]`.
- Operational outputs: item create/update/delete/move/import and Excel API write flows emit Telegram notifications when integration is enabled.

## Build and deploy
- **CI** (`ci.yml`): lint + tests + Docker build on push/PR.
- **Deploy to Azure** (`deploy.yml`): validates Azure infra, builds/pushes image to GHCR, deploys container to Azure Web App, then runs smoke tests.
- **Device smoke** (`device-smoke.yml`): Playwright smoke tests across Firefox desktop, Android Chrome emulation, and iPhone Safari emulation.

## Azure deployment pipeline setup

This repository already includes `.github/workflows/deploy.yml`, which deploys to **Azure Web App for Containers** using OIDC login (no publish profile required).
The workflow is implemented with shell steps (no third-party GitHub Actions), so it also works when the repository policy allows only owner-local actions.

### 1) Create Azure infrastructure
Create a Linux App Service plan and Web App in your subscription:

```bash
az login
az account set --subscription "<your-subscription-id>"

az group create \
  --name "rg-stockmgr-prod" \
  --location "westeurope"

az appservice plan create \
  --name "asp-stockmgr-prod" \
  --resource-group "rg-stockmgr-prod" \
  --is-linux \
  --sku "B1"

az webapp create \
  --name "stockmgr-prod-<unique-suffix>" \
  --resource-group "rg-stockmgr-prod" \
  --plan "asp-stockmgr-prod" \
  --runtime "PYTHON:3.12"
```

> Use `PYTHON:3.12` (colon), not `PYTHON|3.12` (pipe).  
> You can confirm valid values with `az webapp list-runtimes --os-type linux -o tsv` and filter for `PYTHON` (`grep`/`findstr`/`Select-String` depending on shell).

### 2) Create Entra ID app + service principal for GitHub OIDC

If you use **Bash**:

```bash
APP_CLIENT_ID="$(az ad app create --display-name "stockmgr-gha-deploy" --query appId -o tsv)"
APP_OBJECT_ID="$(az ad app list --display-name "stockmgr-gha-deploy" --query "[0].id" -o tsv)"

az ad sp create --id "$APP_CLIENT_ID"

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
RESOURCE_GROUP="rg-stockmgr-prod"
```

If you use **PowerShell**:

```powershell
$appClientId = az ad app create --display-name "stockmgr-gha-deploy" --query appId -o tsv
$appObjectId = az ad app list --display-name "stockmgr-gha-deploy" --query "[0].id" -o tsv

az ad sp create --id $appClientId

$subscriptionId = az account show --query id -o tsv
$tenantId = az account show --query tenantId -o tsv
$resourceGroup = "rg-stockmgr-prod"
```

Grant deploy permissions (Contributor on the resource group scope):

```bash
az role assignment create \
  --assignee "$APP_CLIENT_ID" \
  --role Contributor \
  --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
```

PowerShell equivalent:

```powershell
az role assignment create --assignee $appClientId --role Contributor --scope "/subscriptions/$subscriptionId/resourceGroups/$resourceGroup"
```

Add federated credentials for this repository/branch:

```bash
cat > federated-main.json <<'JSON'
{
  "name": "stockmgr-main-deploy",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:ruimcoder/stockmgr:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
JSON

az ad app federated-credential create \
  --id "$APP_OBJECT_ID" \
  --parameters @federated-main.json
```

PowerShell equivalent:

```powershell
$federatedCredential = @'
{
  "name": "stockmgr-main-deploy",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:ruimcoder/stockmgr:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}
'@
$federatedCredential | Set-Content -Path "federated-main.json" -Encoding utf8

az ad app federated-credential create --id $appObjectId --parameters '@federated-main.json'
```

If you prefer inline JSON in PowerShell, use either of these safe forms:

```powershell
$federatedCredential = '{"name":"stockmgr-main-deploy","issuer":"https://token.actions.githubusercontent.com","subject":"repo:ruimcoder/stockmgr:ref:refs/heads/main","audiences":["api://AzureADTokenExchange"]}'
az ad app federated-credential create --id $appObjectId --parameters $federatedCredential
```

```powershell
$federatedCredential = "{`"name`":`"stockmgr-main-deploy`",`"issuer`":`"https://token.actions.githubusercontent.com`",`"subject`":`"repo:ruimcoder/stockmgr:ref:refs/heads/main`",`"audiences`":[`"api://AzureADTokenExchange`"]}"
az ad app federated-credential create --id $appObjectId --parameters $federatedCredential
```

> Note: `\"` escaping is for Bash/CMD-style quoting. In native PowerShell, use single-quoted JSON or PowerShell escaping with `` `" ``.

> If you deploy from another branch, create an additional federated credential with that branch in `subject`.

### 3) Configure GitHub repository variables and secrets
Set **Repository Variables** (`Settings -> Secrets and variables -> Actions -> Variables`):

- `AZURE_RESOURCE_GROUP` = `rg-stockmgr-prod`
- `AZURE_APPSERVICE_PLAN` = `asp-stockmgr-prod`
- `AZURE_WEBAPP_NAME` = `stockmgr-prod-<unique-suffix>`
- Optional: `AZURE_APPSERVICE_PLAN_RESOURCE_GROUP` (if different from web app RG)
- Optional app config: `AUTH_MODE`, `CALENDAR_PROVIDER`, `RENEWAL_WINDOW_DAYS`, `ADMIN_EMAILS`, `EXCEL_API_USER_EMAIL`, `DATABASE_URL`, `PUBLIC_BASE_URL`, `TELEGRAM_ALLOWED_USER_ID`, `TELEGRAM_ALLOWED_CHAT_ID`, `TELEGRAM_REQUIRE_PRIVATE_CHAT`
- For Gmail + Outlook login, set `AUTH_MODE=oauth`.
- If `DATABASE_URL` is not set, deploy workflow defaults to persistent App Service storage: `sqlite:////home/site/data/stockmgr.db`

Set **Repository Secrets**:

- `AZURE_CLIENT_ID` = Entra app client ID (from `az ad app create --query appId`)
- `AZURE_TENANT_ID` = tenant ID (from `az account show --query tenantId`)
- `AZURE_SUBSCRIPTION_ID` = subscription ID (from `az account show --query id`)
- `GHCR_USERNAME` = GitHub username that owns/has access to package
- `GHCR_TOKEN` = GitHub token/PAT with package read access (for Azure pull from GHCR)
- Recommended: `SECRET_KEY`
- Optional: `EXCEL_API_KEY`
- Optional: `TELEGRAM_BOT_TOKEN`
- Optional: `TELEGRAM_WEBHOOK_SECRET`
- OAuth (required when `AUTH_MODE` is `google`, `microsoft`, or `oauth`):
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `MICROSOFT_CLIENT_ID`
  - `MICROSOFT_CLIENT_SECRET`

### 3.1) Configure OAuth providers for gmail.com and outlook.com
1. **Google (gmail.com)**:
   - Google Cloud Console -> `APIs & Services` -> `Credentials` -> create an **OAuth 2.0 Client ID** (Web application).
   - Authorized redirect URI (must match exactly, including `https`):
     - `https://<AZURE_WEBAPP_NAME>.azurewebsites.net/auth/google/callback`
   - Save values to GitHub secrets: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

2. **Microsoft (outlook.com)**:
   - Azure Portal -> `Microsoft Entra ID` -> `App registrations` -> create app.
   - Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**.
   - Add Web redirect URI (must match exactly, including `https`):
     - `https://<AZURE_WEBAPP_NAME>.azurewebsites.net/auth/microsoft/callback`
   - Save values to GitHub secrets: `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`.

### Where each configuration is made
- **Azure Resource Group / App Service Plan / Web App**  
  - Azure Portal: `Resource groups`, `App Services`, `App Service plans`
  - CLI alternative: `az group create`, `az appservice plan create`, `az webapp create`
- **Entra app registration + Service Principal**  
  - Azure Portal: `Microsoft Entra ID -> App registrations` and `Enterprise applications`
  - CLI alternative: `az ad app create`, `az ad sp create`
- **Federated credential for GitHub OIDC**  
  - Azure Portal: `Microsoft Entra ID -> App registrations -> <your app> -> Certificates & secrets -> Federated credentials`
  - CLI alternative: `az ad app federated-credential create`
- **Role assignment (Contributor)**  
  - Azure Portal: `Resource group -> Access control (IAM) -> Add role assignment`
  - CLI alternative: `az role assignment create ... --scope /subscriptions/.../resourceGroups/...`
- **GitHub deployment inputs consumed by workflow**  
  - GitHub Repo: `Settings -> Secrets and variables -> Actions`
  - Variables tab: `AZURE_RESOURCE_GROUP`, `AZURE_APPSERVICE_PLAN`, `AZURE_WEBAPP_NAME`, optional app config values (`DATABASE_URL` supported)
  - Secrets tab: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `GHCR_USERNAME`, `GHCR_TOKEN`, `SECRET_KEY`, `EXCEL_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`
- **Container/runtime settings after deploy**  
  - Written by workflow step **Configure Azure Web App container** in `.github/workflows/deploy.yml`
  - View in Azure Portal: `App Service -> <webapp> -> Settings -> Environment variables`
- **Workflow trigger configuration**  
  - In repo file: `.github/workflows/deploy.yml` (`push` to `main` + `workflow_dispatch`)
  - GitHub UI: `Actions -> Deploy to Azure -> Run workflow` for manual runs

### 4) Run and verify deployment
1. Push to `main` (or run `Deploy to Azure` manually via `workflow_dispatch` on `main`).
2. The workflow will:
   - validate infra with `scripts/azure/validate_infra.sh`
   - build/push image to GHCR
   - configure Web App container + app settings
   - restart app and run `scripts/azure/smoke_test.sh`
3. Confirm the app opens at:
   - `https://<AZURE_WEBAPP_NAME>.azurewebsites.net`
   - `https://<AZURE_WEBAPP_NAME>.azurewebsites.net/health` returns `{"status":"ok","version":"<commit-sha>"}` after deployment
   - The `/health` `version` value should match the SHA shown in the latest successful `Deploy to Azure` run.

### 5) Troubleshooting quick checks
- OIDC login fails: verify federated credential `subject` exactly matches `repo:ruimcoder/stockmgr:ref:refs/heads/main`.
- Infra validation fails: check `AZURE_RESOURCE_GROUP`, `AZURE_APPSERVICE_PLAN`, and `AZURE_WEBAPP_NAME` variable values, and confirm both App Service Plan and Web App are Linux (`az appservice plan show --query kind`, `az webapp show --query kind`; `reserved` may be empty on some SKUs).
- Container pull fails: verify `GHCR_USERNAME`/`GHCR_TOKEN` and package visibility/access.
- Smoke test fails: inspect `scripts/azure/smoke_test.sh` expectations (`/health`, manifest, Excel API auth behavior).
- Manual re-run of an old workflow run: this is now blocked for `push` events to prevent stale commit rollback deployments.
- OAuth buttons missing: ensure `AUTH_MODE` is not `dev` and required OAuth secrets are set in GitHub (`GOOGLE_*`, `MICROSOFT_*`) with correct callback URLs.
- `Error 400: redirect_uri_mismatch` (Google): verify Google redirect URI exactly matches `/auth/google/callback` and set `PUBLIC_BASE_URL` (GitHub Actions variable) to your public HTTPS app URL so runtime-generated callback URIs are stable behind Azure proxying.
- Microsoft callback `server_error`: the app now redirects safely back to `/login` with an OAuth message. If it appears, verify Microsoft Entra app registration redirect URI and API permissions/consent (`User.Read`, calendar scopes).
- Microsoft callback with `code` followed by internal error: issuer-claim validation is now relaxed for Microsoft token exchange to support tenant-specific issuer values from `/common`; callback failures now redirect to `/login` with a message instead of returning 500.
- Data disappears after redeploy: confirm app settings include `WEBSITES_ENABLE_APP_SERVICE_STORAGE=true` and `DATABASE_URL` points to `/home/...` (for example `sqlite:////home/site/data/stockmgr.db`), not a path inside the container image filesystem.
- Telegram webhook returns `403`: verify `TELEGRAM_ALLOWED_USER_ID`, `TELEGRAM_ALLOWED_CHAT_ID`, and `X-Telegram-Bot-Api-Secret-Token` values exactly match app configuration.

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

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for version history.
