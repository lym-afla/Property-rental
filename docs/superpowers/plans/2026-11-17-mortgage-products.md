# Mortgage products implementation plan

**Goal:** File each mortgage product separately without fragmenting the verified balance ledger.
**Architecture:** Owner-scoped LoanProduct metadata under the existing Loan; add an editor/list to the existing Loans page.
**Stack:** Django, DRF, React, TanStack Query, existing form/UI components.
**Spec:** ../specs/2026-11-17-mortgage-products-design.md

## Constraints and review focus

- Existing payment/fee/balance rows and Wealth identifiers must remain unchanged.
- Inclusive adjacent dates must not overlap; unknown rates and dates before legacy Loan start are supported.
- Owner isolation applies to all CRUD operations, destination loan and filters; concurrent mutations serialize on the loan.
- Existing loan terms are copied once for existing users; no private source data is tracked.
- Product notes must clearly distinguish projections, inferred dates and variable-rate changes.

## Tasks

- [x] Backend: regression tests for owner CRUD, interval/rate validation, migration copy, and invariance; run red, add LoanProduct model/migration/serializer/view/routes, run green.
- [x] Frontend: typed LoanProduct/query hooks and product section with distinct chronological entries and add/edit/delete forms; tests for visible historical rates and CRUD/error handling, then implement and verify.
- [x] Integration: version 2.5.0, public documentation of product metadata and compatible Wealth behavior; backend/full frontend/build checks and independent review.
- [ ] Release: PR/checks/merge/tag/exact-source image, Life OS promotion/backup/rehearsal/deploy/acceptance.
- [ ] Private population: preserve original financial evidence, derive known and estimated product periods/opening balances, guarded dry-run and atomic insertion/update after backup, repeat preview and independent production checks.

## Result

Implementation verified: 600 backend tests passed (two PostgreSQL-only local skips); 306 frontend tests, build/typecheck and migration checks passed. Independent review found no actionable findings. Release and private population remain below.
