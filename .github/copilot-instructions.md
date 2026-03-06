# Copilot Instructions for `stockmgr`

Use this repository to build a user-friendly web application for managing SHTF stock inventory.

## Primary source of truth
- Product requirements baseline: `.github/project-requirements.md`
- Provider configuration schema: `config/barcode-providers.schema.json`
- Default provider configuration: `config/barcode-providers.default.json`
- Keep this requirements file up to date as decisions are refined.

## Implementation priorities
1. Start with a maintainable web app foundation.
2. Implement OAuth-based authentication and persistent data storage.
3. Build inventory management around the required fields and workflows.
4. Add calendar appointment integration for renewal dates using configurable providers.
5. Support barcode-based entry, manual entry, data-grid editing, and Excel/CSV import.

## Constraints and expectations
- Preserve existing behavior when adding features; avoid breaking changes.
- Treat provider integrations (calendar and barcode lookup) as configurable.
- Surface errors explicitly; do not silently swallow failures.
- Keep code clear, testable, and easy to extend as requirements evolve.

