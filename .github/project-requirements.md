# Project Requirements Baseline

This document captures the initial application requirements and will be refined over time.

## Product goal
Build a web application to manage SHTF stock items, including shelf-life tracking and rotation planning.

## Core requirements
1. Build a web application with:
   - OAuth authentication
   - Persistent data storage
2. Store inventory records with the following attributes:
   - Item name
   - Item type
   - Storage location
   - Storage bucket
   - Expiry date
   - Temperature storage range
   - Humidity storage range
   - Renewal date(s)
3. Renewal dates must be created as calendar appointments in one configured provider:
   - Google Calendar
   - Outlook Calendar
   - Microsoft 365 Calendar
4. User interface must be user-friendly and support item entry through:
   - Barcode scanning/entry with product data lookup from an external barcode data source
   - Individual/manual item characteristic entry
   - Data-grid view/edit workflow
5. Support file-based imports:
   - Excel import
   - CSV import
6. Support a secure Telegram operations channel for owner communication:
   - Accept Telegram inputs only from the configured owner identity.
   - Validate webhook origin using a shared secret token.
   - Send operation outputs/status summaries back through Telegram.

## Configuration requirements
- Calendar provider must be selected through application configuration.
- Barcode product data source must be configurable to support future provider changes.
- Telegram access control (allowed user/chat IDs and webhook secret) must be configurable.
- Provider configuration contract must be defined by `config/barcode-providers.schema.json`.
- Default provider runtime settings must live in `config/barcode-providers.default.json`.

## Product information providers (initial candidates)
This shortlist is the current baseline and should be revisited as requirements evolve.

### Open/public candidates
1. Open Food Facts
   - Best for: food products and pantry items.
   - Notes: open data under ODbL with attribution/share-alike requirements; published API rate limits.
2. Open Products Facts
   - Best for: non-food general products.
   - Notes: open project in the Open Food Facts family; open-data terms.
3. USDA FoodData Central
   - Best for: US branded food products and nutrition metadata.
   - Notes: free API with key registration; public-domain dataset.
4. openFDA Drug NDC API
   - Best for: US medication/NDC lookup use cases.
   - Notes: public API for drug metadata; useful for medical stock categories.

### Commercial/fallback candidates
1. UPCitemdb
   - Best for: broad barcode lookup with easy API access and free evaluation tier.
2. Go-UPC
   - Best for: broad global product coverage and bulk lookup workflows.
3. GS1 US APIs
   - Best for: high-trust enterprise validation and standards-compliant identifier workflows.
   - Notes: paid subscription model.

### Recommended initial strategy
- Implement a provider abstraction layer and configure priority order by product category.
- Start with Open Food Facts + Open Products Facts for open-data coverage.
- Add USDA FoodData Central and openFDA for US food/medical enrichment.
- Use UPCitemdb/Go-UPC as optional fallback providers where open datasets have gaps.

## Default provider priority (v1)
The application must ship with this default provider order:

1. Open Food Facts (Portugal-first for food)
   - Default query scope must include Portugal products first (country = Portugal), then global fallback.
   - Primary source for pantry and food barcode lookups.
2. Open Products Facts (Portugal-first for non-food)
   - Default query scope must include Portugal products first when available, then global fallback.
   - Primary source for non-food household items.
3. USDA FoodData Central (US food enrichment)
   - Used as enrichment/fallback for missing food metadata.
4. openFDA Drug NDC API (medical items)
   - Used for medication categories and NDC-driven lookups.
5. UPCitemdb, then Go-UPC (commercial fallback chain)
   - Used only when open/public providers return insufficient data.
6. GS1 US APIs (enterprise optional)
   - Optional high-trust provider for paid enterprise workflows.

## Portuguese retail catalog connectors
- Continente and Auchan may be considered as optional connectors for Portugal-specific coverage.
- Default policy: do not rely on retailer scraping as a primary source.
- Only enable retailer connectors through explicit configuration and legal/compliance review of terms of use.
- Any retailer connector must be isolated behind the provider abstraction layer so it can be disabled without affecting core flows.
- Current implementation status: `continente_pt` barcode search scraping support is available and active in the default provider configuration.

## Open refinement areas
- OAuth providers and account model
- Provider health scoring, timeout, and retry policy for fallback chain
- Excel/CSV schema and validation rules
- Notification/reminder behavior for upcoming renewals

## Implementation status (v1.2.3)

### Web application — implemented
- ✅ Web application with OAuth authentication (Google + Microsoft) and local dev mode
- ✅ Persistent SQLite storage with automatic schema migration
- ✅ All required item attributes (name, type, location, bucket, expiry, temperature, humidity, renewal date, barcode, batch code, quantity, unidose fields)
- ✅ Barcode lookup with AJAX-based flow (no page refresh) and configurable provider chain
- ✅ Provider abstraction with priority config in `config/barcode-providers.default.json`
- ✅ Open Food Facts (Portugal-first), Open Products Facts, USDA, openFDA, UPCitemdb, Go-UPC, Continente PT
- ✅ `stopOnSuccess` flag stops chain on first successful match
- ✅ Manual item entry, data-grid view/edit, datagrid column sorting/filtering/paging
- ✅ Excel and CSV import; XLSX export
- ✅ Calendar sync abstraction (Google/Microsoft provider modes)
- ✅ Secure Telegram operations channel with webhook secret + allowed user/chat ID validation
- ✅ Mobile-first responsive UI with PWA support
- ✅ Portuguese and English UI
- ✅ User registration with admin approval workflow
- ✅ Shopping list with quantity-to-buy calculations
- ✅ Renewal plan (expiry-based) with location filter and print/PDF
- ✅ Food wheel chart (Portuguese food wheel distribution) with chart rendered above plan tabs
- ✅ Unidose planning per location
- ✅ Product image upload; nutriscore display; food group colour indicator
- ✅ Backup/restore admin pages
- ✅ Live barcode provider config editing (`/admin/config`)
- ✅ Semantic versioning; application info page (`/admin/info`)
- ✅ Sort direction indicators (↑/↓/⇅) on all table column headers; click to toggle asc/desc
- ✅ Item names are product detail page links across all list views
- ✅ Hover card (Bootstrap popover) with product image + name on item links
- ✅ Nutriscore tooltip and food group colour dot on all list views
- ✅ Static assets served via root-relative paths — no mixed-content blocking on HTTPS
- ✅ REST JSON API for mobile/integration use (`/api/items`, `/api/barcode-lookup`, `/api/excel/stocks`)
- ✅ Telegram operations channel with command-driven inventory queries and push notifications

### Web application — pending / open refinement
- ⏳ Provider health scoring, timeout, and retry policy for fallback chain
- ⏳ Excel/CSV schema validation rules documentation
- ⏳ Calendar appointment creation for renewal dates (abstraction exists; provider wiring pending)
- ⏳ OAuth provider and account model documentation
- ⏳ `/api/items/{id}` GET/PUT/DELETE endpoints (needed for mobile — see issue #106)
- ⏳ Mobile OAuth deep-link redirect support (see issue #107)

---

## Mobile application requirements (React Native + Expo)

A native phone app is planned as a companion to the web application. It will share the same FastAPI backend via the existing JSON REST API (with extensions). See GitHub milestone **"Mobile MVP v0.1"** (issues #106–#115).

### Tech stack
- **Framework**: React Native + Expo (TypeScript strict mode)
- **Routing**: expo-router (file-based)
- **Location in repo**: `mobile/` directory (monorepo)
- **Deep-link scheme**: `stockmgr://`
- **Auth**: OAuth via `expo-web-browser` + system cookie jar (session cookie)

### MVP scope (issues #106–#115)
The first version targets the highest-value mobile-native features:

| Issue | Type | Description |
|-------|------|-------------|
| #106 | API | Extend REST API: GET/PUT/DELETE `/api/items/{id}`, image upload |
| #107 | API | OAuth deep-link redirect for mobile session creation |
| #108 | Mobile Infra | Expo project scaffold in `mobile/` |
| #109 | Mobile Infra | API client (`lib/api.ts`) + TypeScript types |
| #110 | Mobile Infra | Navigation structure (expo-router + tab bar) |
| #111 | Mobile | Authentication screen (OAuth login flow) |
| #112 | Mobile | Inventory list screen (search + pull-to-refresh) |
| #113 | Mobile | Item detail screen (view + delete) |
| #114 | Mobile | Barcode scanner screen (Expo Camera → lookup → form) |
| #115 | Mobile | Add / Edit item form (create + update) |

### Dependency order
`#108` → `#109`, `#110` → `#107`, `#111` → `#112` → `#113`, `#114`, `#115`  
`#106` is required before `#113` (needs GET endpoint) and `#115` (needs PUT endpoint).

### Future mobile scope (post-MVP)
- Push notifications for expiry alerts and upcoming renewal dates
- Offline mode with local SQLite sync
- Stock movement (quantity increment/decrement) screen
- Shopping list view
- Renewal plan view
- Product image capture via camera


