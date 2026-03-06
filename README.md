# stockmgr

Web MVP to manage SHTF stock inventory with OAuth-capable authentication, barcode-assisted item entry, CSV/XLSX import, renewal-date calendar sync, and configurable product-information providers.

## MVP capabilities
- OAuth-capable auth (Google/Microsoft) plus local development login mode.
- Mandatory fields: type, name, storage location, expiry date.
- Inventory fields: item name/type, location, bucket (optional), batch code (optional), expiry date, temperature range, humidity range, renewal date, barcode.
- Supports multiple batches of the same product (same product/barcode with different batch codes and expiry dates).
- Supports stock quantity per batch, including increment/decrement operations with optional notes and movement logs.
- Supports unidose planning fields (`unidose_per_pack`, `target_unidoses_location`) and automatic unidoses delta calculations per location.
- Barcode lookup endpoint backed by provider-priority config (Portugal-first defaults).
- User-friendly web UI for manual entry, barcode-assisted entry, camera barcode scanning with automatic search submit, datagrid listing/editing, and file import.
- Multilanguage UI switcher (Portuguese and English).
- Stock views include: per product overall, per product and storage location, and per product/location/expiry.
- Stock list supports filtering by bucket assignment (assigned/unassigned) and storage location.
- Shopping list computes quantity-to-buy totals and per-location distribution.
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
```

## Build and deploy
- **CI** (`ci.yml`): lint + tests + Docker build on push/PR.
- **Deploy** (`deploy.yml`): builds and pushes container image to `ghcr.io/<owner>/<repo>` on `main` or manual dispatch.
- Optional: set `DEPLOY_WEBHOOK_URL` secret to trigger your hosting deployment after image publish.

## Agent and requirements docs
- Copilot instructions: `.github/copilot-instructions.md`
- Requirements baseline: `.github/project-requirements.md`
