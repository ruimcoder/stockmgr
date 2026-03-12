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
- Current implementation status: `continente_pt` barcode search scraping support is available in the provider layer, but disabled by default pending explicit enablement.

## Open refinement areas
- OAuth providers and account model
- Provider health scoring, timeout, and retry policy for fallback chain
- Excel/CSV schema and validation rules
- Notification/reminder behavior for upcoming renewals

