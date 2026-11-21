# Changelog

## 2.6.0 — 2026-11-21

- Add an opt-in shared FX mirror and sync command for rental calculations.
- Browse shared reference rates by pair and date range with pinned pagination and read-only provenance details.
- Preserve typed incomplete tenant analytics and document named mirror financial differences.
- Export private, provenance-pinned legacy/mirror report comparisons with deterministic horizons, counterfactual attribution and read-only snapshots.
- Include original lease calendars and deposit, capital and rent facts to verify complete dated currency-pair coverage.

## 2.5.1 — 2026-11-17

- Show the mortgage lender and product active on each valuation date, with explicit missing-history and retry states.

## 2.5.0 — 2026-11-17

- File separate dated mortgage products with lender, rate, opening balance and source notes while keeping payment and balance history continuous.

## 2.4.1 — 2026-11-16

- Restore dashboard cash-flow, cumulative cash, and revenue/expenses charts for portfolios with loan principal payments.

## 2.4.0 — 2026-11-16

- Record dated capitalised loan fees without cash transactions, and include them in debt reconciliation.
- Manage capitalised fees on the property Loans tab through an owner-scoped API.

## 2.3.1 — 2026-11-16

- Sort property valuation history chronologically, including older observations entered later.
- Update the Wealth export handoff and document estimated mortgage-history entries.

## 2.3.0 — 2026-11-14

- Track property loans, split mortgage payments into interest and principal, and reconcile debt history.
- Export complete Rent history to Wealth v1.1 using read-only database access and content versions.
- Add source timestamps and validated CSV mortgage payment imports; preserve legacy SQLite imports.

## 2.2.0 — 2026-11-01

- Sort transactions using accessible column headers, including numeric amounts and property/tenant names.
- Default new transaction currencies to the selected property's native currency while preserving manual overrides.
- Show current tenants by default, with a toggle to include former tenants and preserved historical assignments on edit.
- Preserve a transaction's saved accounting period when opening it for editing.
- Add the teal Rent home icon and consistent browser title in development and production.

## 2.1.2 — 2026-10-14

- Versioning introduced (see `AGENTS.md`); this is the baseline version.
- Tenant security deposits: deposit ledger, tenant and property deposit views, deposits in net cash flow.
