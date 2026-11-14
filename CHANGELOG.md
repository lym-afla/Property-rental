# Changelog

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
