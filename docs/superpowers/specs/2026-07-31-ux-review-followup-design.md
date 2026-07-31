# UX Review Follow-up Design

**Date:** 2026-07-31  
**Status:** Approved in design review with one accounting presentation change  
**Worktree:** `D:\Developing\Property-rental\.worktrees\ux-review-followup-20260731`  
**Scope:** Dashboard, property details, tenant details, transactions, financial semantics, and chart presentation fixes from the second UX review round.

## 1. Context

The investment-performance dashboard now has typed backend analytics, React/Recharts presentation components, accounting-style formatting, property breakdown analytics, and responsive chart/table surfaces. The follow-up review identified remaining issues in metric definitions, P&L structure, valuation display, tenant FX handling, and transaction sign normalization.

The important product constraint is that the app remains a dense analytical workspace that is fully mobile-ready. Fixes should therefore preserve exact-value tables, accessible controls, responsive overflow behavior, and backend-owned financial semantics.

## 2. Goals

1. Make P&L statements consistent on Dashboard and Property details.
2. Keep cost reimbursement as a positive expense-section entry, not revenue.
3. Ensure cost transaction inserts save with canonical signs.
4. Redefine yield calculations so both yield series use the same net-income numerator.
5. Improve yield-definition affordance and tooltips.
6. Improve property valuation form labels, omitted debt handling, sparse timeline display, and subtitle copy.
7. Diagnose and fix tenant rent-performance FX direction issues, especially RUB/GBP paths.
8. Preserve mobile usability and exact values across all changed surfaces.

## 3. Non-goals

- No new dashboard sections.
- No drag-and-drop dashboard customization.
- No new charting library.
- No complete transaction-category model rewrite.
- No forecasting or valuation prediction beyond a bounded start-point interpolation for sparse valuation charts.
- No data cleanup outside the specifically identified cost-reimbursement sign normalization.

## 4. Chosen Architecture

Use backend-owned financial semantics with small frontend presentation changes.

Django remains responsible for category classification, transaction sign normalization, P&L row construction, yield formulas, valuation interpolation metadata, and tenant FX conversion. React remains responsible for labels, tooltips, chart/table rendering, responsive layout, and accessible controls.

This keeps Dashboard, Property details, Tenant details, Transactions, and future API consumers aligned. It also avoids patching values in React after strict Zod validation has already accepted a backend response.

## 5. Alternatives Considered

### Option A — Backend semantic fix with focused frontend presentation updates

This is the selected approach.

Pros:

- One canonical source for category signs and yield definitions.
- Fixes current and future API writes.
- Allows regression tests at the calculation boundary.
- Keeps React simple and display-focused.

Cons:

- Requires coordinated backend and frontend test updates.
- May require a small data migration for existing cost-reimbursement rows.

### Option B — Frontend-only formatting patches

Pros:

- Fewer backend files touched.
- Fastest visible UI change.

Cons:

- Leaves APIs semantically inconsistent.
- Dashboard, property detail, and exported/API values can diverge.
- Does not fix future transaction inserts.

Rejected.

### Option C — Full transaction-category accounting refactor

Pros:

- Could model income, expenses, contra-expenses, capital items, and interest more formally.

Cons:

- Larger than the review comments require.
- Higher migration and regression risk.
- Would slow down the current UX correction work.

Rejected for this scope.

## 6. Financial Category and Sign Semantics

### 6.1 Canonical category roles

Canonical roles:

- `rent` remains an income category.
- `cost_reimbursement` remains an expense-section category but is a positive contra-expense.
- All other current non-income categories are ordinary expense categories.

This means `cost_reimbursement` appears below the visual gap in the P&L expense section, not above `Total revenue`.

### 6.2 Transaction save behavior

When a transaction is created or updated:

- `cost_reimbursement` saves as a positive amount and `type='expense'`.
- Ordinary expense categories save as negative amounts and `type='expense'`, regardless of the sign entered by the user.
- Income categories keep `type='income'`; rent correction behavior is not changed in this scope.

Existing `cost_reimbursement` rows should be normalized by a data migration to positive amounts and `type='expense'`, because production P&L currently reflects negative reimbursements.

### 6.3 Analytics signed values

Analytics should use a shared signed-value helper:

- income category values are included in revenue as their stored signed amount;
- `cost_reimbursement` values are included in expense rows as `abs(amount)`;
- ordinary expense values are included in expense rows as `-abs(amount)`.

P&L `Total expenses` is the sum of all expense-section rows. Because reimbursements are positive contra-expenses, they reduce net expenses. Example: tax `(1,000)` plus reimbursement `250` gives `Total expenses (750)`.

For yield and contribution calculations, net costs should be derived from the signed expense total. Reimbursements reduce costs; they do not increase revenue.

## 7. P&L Statement Design

The same backend P&L response feeds Dashboard and Property details.

### 7.1 Columns

Remove the separate `YTD` column. The current-year annual column becomes year-to-date by label:

- prior full years: `2023`, `2024`, `2025`;
- current partial year: `2026YTD`.

The internal column key may remain the year string, for example `2026`, to avoid unnecessary frontend schema churn, but the displayed label must include `YTD` for the current year.

### 7.2 Rows

Rows are emitted in this order:

1. revenue rows;
2. `Total revenue`;
3. a visual separator/gap;
4. expense rows, including positive `Cost reimbursement`;
5. `Total expenses`;
6. `Net income`.

Expense rows sort by largest absolute impact across the displayed columns. This makes the largest expense drivers appear first while keeping positive cost reimbursements within the expense block.

The frontend table should use the backend row order and add the visual gap before the first expense row after `Total revenue`. It should not reorder or reclassify categories client-side.

## 8. Yield Comparison Design

### 8.1 Formulas

Both yield series use the same numerator:

`annualized net income = annualized revenue - annualized net costs`

Definitions:

- Gross yield = annualized net income divided by latest property value.
- Equity yield = annualized net income divided by latest equity.
- Equity = latest property value less latest debt.

The label `Gross yield` is retained because the user explicitly requested redefining it rather than renaming the series. The definition copy must make the numerator clear.

Costs include all expense categories represented in transaction analytics. If interest is represented as an expense transaction category now or in the future, it is included in net costs.

### 8.2 Tooltip and definition affordance

The yield definition control becomes a standard circular information affordance:

- icon-sized button;
- shaded/circled `i`;
- accessible name `Yield definitions`;
- minimum 44px touch target.

The tooltip must not show an uninformative `Property -` line. It should show the property name as the tooltip title and only meaningful yield series rows below it.

## 9. Property Valuation Design

### 9.1 New valuation form

Field labels:

- `Date`
- `Total value`
- `Debt`

Omitted or blank `Debt` is treated as `0` in the frontend form and backend serializer. This protects both browser and API writes.

### 9.2 Valuation chart subtitle and sparse timeline

Remove this subtitle text:

`Server-provided valuation records; no client-side time cutoff.`

The chart should still communicate the visible date range concisely where useful, for example `All time: 2004-01-01 to 2026-07-31`.

The chart time axis remains a linear time scale. Sparse points such as 2004 then 2023 must show the real gap.

The chart domain should be padded so the first bar does not overlap the vertical axis.

### 9.3 Start-point approximation

The property valuation analytics endpoint should accept an optional `start` date in addition to `end`.

When a requested chart window starts between two existing valuation records, the backend should add a synthetic start point calculated by linear interpolation between the surrounding records. The point must be marked as interpolated so it is not confused with an actual valuation record.

If only a prior record exists before `start`, the backend may carry forward the latest available value and mark it as carried forward. If no prior record exists, it should not fabricate a starting value.

The frontend should display the synthetic point in the chart and table with status text, while preserving actual record dates.

## 10. Tenant Rent Performance Design

Tenant rent performance remains in the tenant/property native currency, not the dashboard reporting currency.

Regression coverage must include:

- RUB property with RUB rent and RUB receipt: no FX lookup and output remains RUB.
- RUB property with GBP rent/receipt: GBP to RUB multiplies through the available FX path.
- GBP property with RUB rent/receipt: RUB to GBP divides through the available FX path.

This directly targets the Анна Коршунова failure mode where RUB/GBP appears to be using the inverse direction.

If those regression tests pass without a code change, the implementation must inspect the actual affected data path next, because the likely cause would then be an older lease-rent row or transaction row stored with the wrong currency. The UI must not hide that by silently overriding persisted currencies.

Chart coloring remains plain color-series mapping. Do not use dashed bars, patterned marks, or dot/line categories to distinguish the main bar series.

## 11. Transactions Design

The Transactions form keeps user-friendly category labels in the table and category selector.

Backend save behavior is canonical:

- cost categories save negative;
- `Cost reimbursement` saves positive;
- signs are normalized regardless of the sign typed by the user.

The frontend may keep the amount placeholder permissive, but backend tests must prove the saved value is canonical.

## 12. Formatting and Mobile Requirements

Negative numbers continue to use accounting format with the currency symbol inside brackets, for example `(£1,234)`. This is the common format in financial statements and is already the app’s current formatter behavior.

All touched controls keep at least 44px touch targets. P&L tables remain horizontally scrollable on mobile with sticky category labels. Essential values must remain available in table mode and cannot require hover.

## 13. Testing Strategy

Backend tests:

- transaction model/API sign normalization;
- data migration for existing `cost_reimbursement` rows;
- P&L columns, row order, positive reimbursement as contra-expense, totals, and property scope;
- yield formulas using net-income numerator for both denominators;
- property valuation omitted debt default and optional interpolated start point;
- tenant rent-performance RUB/GBP direct and reverse conversion paths.

Frontend tests:

- P&L table displays `2026YTD`, no duplicate `YTD`, and visual gap after `Total revenue`;
- FinancialDefinitions renders a circular info affordance and updated copy;
- YieldComparisonChart tooltip filters out non-informative rows;
- PropertyValuationForm labels and blank debt normalization;
- ValuationChart subtitle removal and padded time domain behavior;
- RentPerformanceChart native currency and plain-color series rendering;
- Transactions table/category selector user-friendly labels remain intact.

Verification commands:

- `uv run pytest -q`
- `uv run python property_rental/manage.py check`
- `npm run lint`
- `npm test -- --run`
- `npm run build`

Because a fresh worktree may not have built frontend static assets yet, `manage.py check` can warn about a missing `property_rental/rentals/static` directory until `npm run build` has produced the frontend assets.

## 14. Definition of Done

1. Cost reimbursement appears as a positive expense-section row in Dashboard and Property detail P&L.
2. `Total revenue`, `Total expenses`, and `Net income` reconcile with contra-expense reimbursement behavior.
3. P&L has no duplicate standalone YTD column.
4. Yield definitions and calculations match the new net-income numerator formulas.
5. Yield tooltip no longer shows `Property -`.
6. Property valuation form uses `Date`, `Total value`, and `Debt`; blank debt saves as `0`.
7. Valuation chart uses a padded linear time axis and does not show the removed server-calculation subtitle.
8. Optional valuation start windows can show marked interpolated or carried-forward start points.
9. Tenant rent performance handles RUB/GBP direction correctly in native currency.
10. New cost transactions save with canonical signs.
11. Backend and frontend verification commands pass.

## 15. Decisions Closed

- Cost reimbursement stays in the expense section.
- Cost reimbursement is positive and reduces total expenses.
- Cost reimbursement does not increase revenue.
- Yield formulas use the same net-income numerator and different denominators.
- The literal `(i)` control becomes a proper circular information affordance.
- Valuation debt defaults to `0` when omitted.
- Sparse valuation timelines use real linear time spacing, not equally spaced categories.
