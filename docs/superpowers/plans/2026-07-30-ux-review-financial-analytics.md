# Financial Analytics UX Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the dashboard, property, tenant, and transaction financial UX so calculations are trustworthy, tables are restored, charts use clean color-only series styling, and every surface remains fully usable on mobile.

**Architecture:** Django analytics services remain the source of truth for debt, equity, yields, P&L periods, rent schedules, FX conversion, and property breakdown timelines. DRF exposes explicit typed contracts; React validates those contracts with Zod and owns responsive presentation through shared formatting, category-label, chart-theme, P&L-table, and definition-popover components. Portfolio and property P&L use one backend calculation path, while tenant performance is returned in the property's native currency.

**Tech Stack:** Django 4.2, Django REST Framework, pytest, React 19, TypeScript, TanStack Query, Zod, Recharts, shadcn/Radix UI, Vitest/Testing Library, Playwright, uv, npm.

## Global Constraints

- The dashboard filter card is collapsed by default at every viewport width and exposes the active selection in a compact summary.
- Chart data series use distinct solid colors only: no patterned fills, dashed series, or category marker shapes. Grid lines may remain subtle because they are not data series.
- Preserve non-color accessibility through text legends, direct labels, tooltips, exact-value tables, and accessible series names.
- All negative monetary values use accounting format with the currency symbol inside the parentheses, for example `($1,234)`, `(£1,234)`, and `(₽1,234)`.
- Missing financial values render as an em dash, never as zero or `NaN`.
- Gross yield is annualized gross rental income divided by property value.
- Equity yield is annualized income net of costs divided by equity, where equity equals property value less debt; non-positive or unavailable equity produces no yield.
- Tenant rent performance is calculated and displayed in the property's native currency.
- Property valuation dates use a continuous time scale so horizontal distance is proportional to elapsed calendar time.
- Every new or changed financial table must support horizontal scrolling with its first descriptive column sticky on narrow screens.
- Existing unrelated working-tree changes, including `property_rental/rentals/migrations/0021_alter_transaction_category.py`, must not be modified or committed unless their ownership and purpose are confirmed during execution.

---

## File Structure

- `property_rental/rentals/analytics/pnl.py` — shared annual/YTD, category-level P&L calculation for portfolio and property scopes.
- `property_rental/rentals/analytics/portfolio.py` — portfolio summary, yield, and property-breakdown time-series calculations.
- `property_rental/rentals/analytics/tenant.py` — contractual expected/received/arrears calculations in native currency.
- `property_rental/rentals/api/analytics_serializers.py`, `analytics_views.py`, `urls.py` — strict API contracts and routes for P&L, revised yields, and property breakdown.
- `frontend/src/lib/format.ts` — one accounting formatter for all monetary surfaces.
- `frontend/src/lib/transactionCategories.ts` — canonical frontend category keys and human-readable labels.
- `frontend/src/components/analytics/chartTheme.ts` — solid, sufficiently distinct series palette.
- `frontend/src/components/analytics/FinancialDefinitions.tsx` — accessible `(i)` popover for financial definitions.
- `frontend/src/components/analytics/ProfitLossTable.tsx` — reusable responsive P&L statement.
- Dashboard, property, tenant, and transaction feature files consume these shared primitives without recomputing financial metrics.

### Task 1: Standardize Accounting and Category Presentation

**Files:**
- Create: `frontend/src/lib/transactionCategories.ts`
- Create: `frontend/src/lib/transactionCategories.test.ts`
- Modify: `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/format.test.ts`

**Interfaces:**
- Consumes: Canonical keys from `rentals.constants.TRANSACTION_CATEGORIES`.
- Produces: `formatAccounting(value, currency): string`, `TRANSACTION_CATEGORIES`, and `transactionCategoryLabel(key): string` for all later UI tasks.

- [ ] **Step 1: Write failing accounting-format tests**

```ts
expect(formatAccounting(-1234, 'USD')).toBe('($1,234)')
expect(formatAccounting(-1234, 'GBP')).toBe('(£1,234)')
expect(formatAccounting(-1234, 'RUB')).toBe('(₽1,234)')
expect(formatAccounting(1234, 'USD')).toBe('$1,234')
expect(formatAccounting(null, 'USD')).toBe('—')
expect(formatAccounting(Number.NaN, 'USD')).toBe('—')
```

- [ ] **Step 2: Run the formatter tests and verify the existing outside-parenthesis convention fails**

Run: `npm test -- --run src/lib/format.test.ts`

Expected: FAIL because the current formatter returns `$(1,234)`.

- [ ] **Step 3: Implement the canonical accounting formatter**

```ts
const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$', EUR: '€', GBP: '£', RUB: '₽',
}

export function formatAccounting(
  value: number | string | null | undefined,
  currency: string,
): string {
  if (value === null || value === undefined) return '—'
  const amount = typeof value === 'string' ? Number(value) : value
  if (!Number.isFinite(amount)) return '—'
  const rendered = `${CURRENCY_SYMBOLS[currency] ?? ''}${Math.abs(amount).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  return amount < 0 ? `(${rendered})` : rendered
}
```

- [ ] **Step 4: Write failing category-label tests**

```ts
expect(transactionCategoryLabel('cost_reimbursement')).toBe('Cost reimbursement')
expect(transactionCategoryLabel('other_expenses')).toBe('Other expenses')
expect(transactionCategoryLabel('unknown_key')).toBe('Unknown key')
expect(TRANSACTION_CATEGORIES.map(({ value }) => value)).toContain('rent')
```

- [ ] **Step 5: Implement the shared category registry and safe fallback**

```ts
export const TRANSACTION_CATEGORIES = [
  { value: 'rent', label: 'Rent' },
  { value: 'tax', label: 'Tax' },
  { value: 'capex', label: 'Capex' },
  { value: 'management', label: 'Management' },
  { value: 'electricity', label: 'Electricity' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'internet', label: 'Internet' },
  { value: 'cost_reimbursement', label: 'Cost reimbursement' },
  { value: 'other_expenses', label: 'Other expenses' },
] as const

export function transactionCategoryLabel(key: string): string {
  return TRANSACTION_CATEGORIES.find(({ value }) => value === key)?.label
    ?? key.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())
}
```

- [ ] **Step 6: Run the focused tests and commit**

Run: `npm test -- --run src/lib/format.test.ts src/lib/transactionCategories.test.ts`

Expected: PASS.

```powershell
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts frontend/src/lib/transactionCategories.ts frontend/src/lib/transactionCategories.test.ts
git commit -m "fix: standardize financial and category formatting"
```

### Task 2: Replace Patterned and Dashed Data-Series Styling with Solid Colors

**Files:**
- Modify: `frontend/src/components/analytics/chartTheme.ts`
- Modify: `frontend/src/components/analytics/ChartLegend.tsx`
- Modify: all files under `frontend/src/features/dashboard/charts/`
- Modify: `frontend/src/features/property/ValuationChart.tsx`
- Modify: `frontend/src/features/tenant/RentPerformanceChart.tsx`
- Delete after removing all imports: `frontend/src/components/analytics/ChartPatternDefs.tsx`
- Test: `frontend/src/components/analytics/ChartLegend.test.tsx`
- Test: affected `*.test.tsx` chart files

**Interfaces:**
- Consumes: `AnalyticsSeriesDefinition.visualToken`.
- Produces: `chartSeriesStyle(token).color` from a nine-color solid palette; legends remain toggles but show uniform square color swatches.

- [ ] **Step 1: Replace tests that expect patterns, dashes, dots, or marker-shape differences with solid-color assertions**

```ts
expect(new Set(series.map((item) => chartSeriesStyle(item.visualToken).color)).size)
  .toBe(series.length)
expect(screen.getByTestId('legend-marker-rent')).toHaveAttribute('data-marker', 'swatch')
expect(screen.getByTestId('revenue-line')).not.toHaveAttribute('stroke-dasharray')
expect(screen.getByTestId('expense-line')).not.toHaveAttribute('stroke-dasharray')
expect(screen.getByTestId('valuation-bar-Debt').getAttribute('data-fill')).not.toMatch(/^url\(/)
```

- [ ] **Step 2: Run chart tests and verify they fail against the current patterned/dashed theme**

Run: `npm test -- --run src/components/analytics/ChartLegend.test.tsx src/features/dashboard/charts src/features/property/ValuationChart.test.tsx src/features/tenant/RentPerformanceChart.test.tsx`

Expected: FAIL on patterned fills, marker identities, and dash arrays.

- [ ] **Step 3: Define nine solid colors and simplify the style type**

```ts
export type ChartSeriesStyle = { color: string; strokeWidth: number }

const colors = [
  '#2563EB', '#D97706', '#059669', '#7C3AED', '#DC2626',
  '#0891B2', '#C026D3', '#65A30D', '#475569',
] as const
```

Map each visual token to one unique `color`, remove `marker`, `strokeDasharray`, and `chartPatternFill`, and use the slate fallback only for undeclared tokens.

- [ ] **Step 4: Render all series with direct solid colors**

```tsx
<Bar fill={chartSeriesStyle(item.visualToken).color} />
<Line
  stroke={chartSeriesStyle(item.visualToken).color}
  strokeWidth={chartSeriesStyle(item.visualToken).strokeWidth}
  dot={false}
/>
```

Remove every `ChartPatternDefs`, `chartPatternFill`, series `strokeDasharray`, and data-point `dot` use. Keep `CartesianGrid strokeDasharray="3 3"`; it is scaffolding, not category encoding. Give revenue and expenses separate colors and solid lines.

- [ ] **Step 5: Keep non-color accessibility in legend and exact values**

Render one square swatch, the full text label, `aria-pressed`, strikethrough when hidden, tooltips, and the table toggle. Do not encode series categories with dots, lines, or shape names in the legend.

- [ ] **Step 6: Run the focused chart suite and commit**

Run: `npm test -- --run src/components/analytics src/features/dashboard/charts src/features/property/ValuationChart.test.tsx src/features/tenant/RentPerformanceChart.test.tsx`

Expected: PASS.

```powershell
git add frontend/src/components/analytics frontend/src/features/dashboard/charts frontend/src/features/property/ValuationChart.tsx frontend/src/features/property/ValuationChart.test.tsx frontend/src/features/tenant/RentPerformanceChart.tsx frontend/src/features/tenant/RentPerformanceChart.test.tsx
git commit -m "style: use solid colors for chart series"
```

### Task 3: Collapse Dashboard Settings and Fix Filter Spacing

**Files:**
- Modify: `frontend/src/features/dashboard/DashboardFilters.tsx`
- Test: `frontend/src/features/dashboard/DashboardFilters.test.tsx`
- Modify: `frontend/e2e/investment-dashboard.spec.ts`

**Interfaces:**
- Consumes: Existing `DashboardFilterState` and property options.
- Produces: collapsed-by-default `DashboardFilters` with a summary line and an explicit `Show settings`/`Hide settings` button.

- [ ] **Step 1: Write failing desktop and mobile interaction tests**

```tsx
expect(screen.queryByLabelText('Start date')).not.toBeInTheDocument()
expect(screen.getByText('Jan 1, 2026–Jul 30, 2026 · USD · Monthly · All properties')).toBeVisible()
await user.click(screen.getByRole('button', { name: 'Show settings' }))
expect(screen.getByLabelText('Start date')).toBeVisible()
expect(screen.getByLabelText('Properties')).toBeVisible()
await user.click(screen.getByRole('button', { name: 'Hide settings' }))
expect(screen.queryByLabelText('Start date')).not.toBeInTheDocument()
```

- [ ] **Step 2: Run the filter tests and verify the always-expanded card fails them**

Run: `npm test -- --run src/features/dashboard/DashboardFilters.test.tsx`

Expected: FAIL because all controls are currently mounted visibly.

- [ ] **Step 3: Implement the disclosure and compact active-filter summary**

Use a native button with `aria-expanded` and `aria-controls="dashboard-settings"`. Keep state local and initially `false`; URL filters remain the durable source of filter values. The collapsed row contains the summary and button, while `#dashboard-settings` contains the existing desktop controls or mobile sheet trigger.

- [ ] **Step 4: Correct the Properties label/control geometry**

```tsx
<div className="grid gap-1.5 text-xs font-medium text-muted-foreground">
  <span>Properties</span>
  <DropdownMenu>{/* trigger and choices */}</DropdownMenu>
</div>
```

Use `gap-3` between filter groups, `gap-1.5` between a label and its control, no negative margins, and allow the property trigger to grow to `min-w-40` without colliding with its label.

- [ ] **Step 5: Add Playwright checks at 390, 768, and 1440 pixels**

Assert collapsed initial state, settings expansion, 44-pixel minimum controls, no horizontal page overflow, and a visible non-overlapping Properties label and selector.

- [ ] **Step 6: Run tests and commit**

Run: `npm test -- --run src/features/dashboard/DashboardFilters.test.tsx`

Run: `npx playwright test e2e/investment-dashboard.spec.ts`

Expected: PASS.

```powershell
git add frontend/src/features/dashboard/DashboardFilters.tsx frontend/src/features/dashboard/DashboardFilters.test.tsx frontend/e2e/investment-dashboard.spec.ts
git commit -m "fix: collapse dashboard settings by default"
```

### Task 4: Correct Portfolio Debt, Equity, and Equity Yield Contracts

**Files:**
- Modify: `property_rental/rentals/analytics/portfolio.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Test: `property_rental/rentals/tests/test_analytics_portfolio.py`
- Test: `property_rental/rentals/tests/test_analytics_api.py`
- Modify: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/api/analytics.test.tsx`
- Modify: `frontend/src/features/dashboard/charts/YieldComparisonChart.tsx`
- Test: `frontend/src/features/dashboard/charts/YieldComparisonChart.test.tsx`
- Create: `frontend/src/components/analytics/FinancialDefinitions.tsx`
- Test: `frontend/src/components/analytics/FinancialDefinitions.test.tsx`

**Interfaces:**
- Consumes: Latest non-null `capital_structure_value` and `capital_structure_debt` at or before `filters.end`, with independent snapshot dates.
- Produces: `YieldRow.equity`, `YieldRow.equity_yield`, explicit denominator status, and a dashboard definitions popover.

- [ ] **Step 1: Add failing portfolio-summary snapshot tests**

Create two active properties with non-zero values and debts, including value and debt entered on different dates. Assert converted portfolio debt is the sum of latest eligible debt snapshots and equity is converted value less converted debt. Add a missing-debt property and assert `debt is None`, `equity is None`, and status is `missing_valuation`, never numeric zero.

```python
assert result.property_value == pytest.approx(900_000)
assert result.debt == pytest.approx(350_000)
assert result.equity == pytest.approx(550_000)
```

- [ ] **Step 2: Add failing equity-yield tests**

```python
assert row.gross_yield == pytest.approx(annualized_revenue / value * 100)
assert row.equity == pytest.approx(value - debt)
assert row.equity_yield == pytest.approx(
    (annualized_revenue - annualized_costs) / (value - debt) * 100
)
```

Add zero-equity, negative-equity, missing-debt, missing-value, stale-value, and stale-debt cases. Yield fields must be `None` whenever their own denominator is unavailable or non-positive.

- [ ] **Step 3: Run backend tests and record the failing calculation/contract evidence**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py property_rental/rentals/tests/test_analytics_api.py -q`

Expected: FAIL because yield rows lack debt/equity and `net_yield` divides by property value.

- [ ] **Step 4: Implement independent capital snapshot conversion and equity yield**

Extend `YieldRow` with:

```python
debt: float | None
equity: float | None
equity_yield: float | None
```

For every property, select latest non-null value and debt independently as of `filters.end`, convert each using its snapshot date rather than blindly using the report end date, calculate `equity = property_value - debt`, and calculate equity yield only when `equity > 0`. Rename the serialized `net_yield` field to `equity_yield`; do not retain a misleading compatibility alias because the frontend and backend ship together.

- [ ] **Step 5: Tighten DRF and Zod schemas**

```ts
debt: z.number().nullable(),
equity: z.number().nullable(),
gross_yield: z.number().nullable(),
equity_yield: z.number().nullable(),
```

Assert invalid `NaN`, omitted denominators, and legacy `net_yield` payloads fail parsing.

- [ ] **Step 6: Update the yield chart and eliminate the `Property NaN%` path**

Use the keys `gross_yield` and `equity_yield`, labels `Gross yield` and `Equity yield`, and only materialize scatter points for finite numbers. Tooltip labels must use `row.property_name`; never coerce a missing point with `Number(null)` or `Number(undefined)`.

- [ ] **Step 7: Add the accessible definitions popover**

Place an `(i)` button beside “Yield comparison”. Its dialog/popover text is:

- Gross yield — annualized gross rental income divided by the latest property value.
- Equity yield — annualized rental income net of costs divided by equity.
- Equity — latest property value less latest debt, using records available as of the selected date.

The button has `aria-label="Yield definitions"`, opens by keyboard/touch/click, traps no focus after dismissal, and has at least a 44-pixel touch target.

- [ ] **Step 8: Run backend/frontend tests and commit**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py property_rental/rentals/tests/test_analytics_api.py -q`

Run: `npm test -- --run src/api/analytics.test.tsx src/features/dashboard/charts/YieldComparisonChart.test.tsx src/components/analytics/FinancialDefinitions.test.tsx`

Expected: PASS.

```powershell
git add property_rental/rentals/analytics/portfolio.py property_rental/rentals/api/analytics_serializers.py property_rental/rentals/tests/test_analytics_portfolio.py property_rental/rentals/tests/test_analytics_api.py frontend/src/types/analytics.ts frontend/src/api/analytics.test.tsx frontend/src/features/dashboard/charts/YieldComparisonChart.tsx frontend/src/features/dashboard/charts/YieldComparisonChart.test.tsx frontend/src/components/analytics/FinancialDefinitions.tsx frontend/src/components/analytics/FinancialDefinitions.test.tsx
git commit -m "fix: calculate portfolio equity and equity yield"
```

### Task 5: Restore a Shared Annual and YTD Profit & Loss Statement

**Files:**
- Create: `property_rental/rentals/analytics/pnl.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Create: `property_rental/rentals/tests/test_analytics_pnl.py`
- Modify: `property_rental/rentals/tests/test_analytics_api.py`
- Modify: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/api/analytics.ts`
- Modify: `frontend/src/api/keys.ts`
- Modify: `frontend/src/api/analytics.test.tsx`
- Create: `frontend/src/components/analytics/ProfitLossTable.tsx`
- Create: `frontend/src/components/analytics/ProfitLossTable.test.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Modify: `frontend/src/pages/HomePage.test.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.test.tsx`

**Interfaces:**
- Consumes: user, reporting currency, end date, and optional property IDs.
- Produces: `profit_and_loss(user, end, currency, property_ids=()) -> ProfitLossResponse` and `useProfitLoss({end, currency, propertyIds})`.

- [ ] **Step 1: Write failing shared P&L service tests**

Use transactions across three years, multiple categories, two properties, and mixed currencies. Assert annual columns from the earliest transaction year through the selected end year plus a final YTD column from January 1 through `end`. Assert expense values are signed negative, missing category/year intersections are zero, and totals reconcile:

```python
assert result.columns[-1].key == "ytd"
assert result.rows_by_key["rent"].values["2024"] == pytest.approx(24_000)
assert result.rows_by_key["tax"].values["2024"] == pytest.approx(-2_000)
assert result.total_revenue["2024"] + result.total_expenses["2024"] \
    == pytest.approx(result.net_income["2024"])
```

Run the same assertions with `property_ids=(property_a.id,)` and confirm property B is excluded.

- [ ] **Step 2: Run backend P&L tests and verify the service is absent**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_pnl.py -q`

Expected: FAIL because `rentals.analytics.pnl` does not exist.

- [ ] **Step 3: Implement the typed P&L response**

```python
@dataclass(frozen=True)
class ProfitLossColumn:
    key: str
    label: str
    start: date
    end: date

@dataclass(frozen=True)
class ProfitLossRow:
    key: str
    label: str
    kind: str
    values: dict[str, float]

@dataclass(frozen=True)
class ProfitLossResponse:
    metric: str
    currency: str
    scale: int
    end: date
    columns: tuple[ProfitLossColumn, ...]
    rows: tuple[ProfitLossRow, ...]
```

Generate category rows in canonical constants order, omit rows that are zero across every column, then append `total_revenue`, `total_expenses`, and `net_income`. Use `preload_converter` once across scoped transactions and convert on each transaction date.

- [ ] **Step 4: Expose and validate the endpoint**

Add `GET /api/analytics/portfolio/profit-loss/?end=YYYY-MM-DD&currency=USD&property=1&property=2`. Reuse analytics ownership/scoping rules and strict nested serializers. API tests cover invalid dates/currencies/property IDs and cross-user property exclusion.

- [ ] **Step 5: Add frontend schema, key, hook, and contract tests**

Define strict discriminated row kinds `income`, `expense`, `total_revenue`, `total_expenses`, and `net_income`; require every row to contain every declared column key; reject undeclared value keys.

- [ ] **Step 6: Build a reusable responsive P&L table**

Render category labels via server labels, year columns chronologically, YTD last, numeric cells with `formatAccounting`, bold/divided total rows, a sticky first column, and horizontal scrolling below desktop width. Its accessible name is `Profit and Loss statement`.

- [ ] **Step 7: Restore the dashboard P&L**

Mount `ProfitLossTable` as an always-visible card at the bottom of the Income & Costs section, using the dashboard end date, reporting currency, and selected properties. Do not hide it behind the chart/table toggle.

- [ ] **Step 8: Replace property YTD KPI tiles with the same statement**

Request the endpoint with `propertyIds: [propertyId]`, delete the “Server-calculated year-to-date performance…” copy, and show full annual history plus YTD using the same component and native property currency.

- [ ] **Step 9: Run focused suites and commit**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_pnl.py property_rental/rentals/tests/test_analytics_api.py -q`

Run: `npm test -- --run src/api/analytics.test.tsx src/components/analytics/ProfitLossTable.test.tsx src/pages/HomePage.test.tsx src/pages/PropertyDetailPage.test.tsx`

Expected: PASS.

```powershell
git add property_rental/rentals/analytics/pnl.py property_rental/rentals/api property_rental/rentals/tests/test_analytics_pnl.py property_rental/rentals/tests/test_analytics_api.py frontend/src/types/analytics.ts frontend/src/api frontend/src/components/analytics/ProfitLossTable.tsx frontend/src/components/analytics/ProfitLossTable.test.tsx frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.test.tsx frontend/src/pages/PropertyDetailPage.tsx frontend/src/pages/PropertyDetailPage.test.tsx
git commit -m "feat: restore shared profit and loss statements"
```

### Task 6: Replace Currency Exposure with Property Portfolio Breakdown

**Files:**
- Modify: `property_rental/rentals/analytics/portfolio.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Test: `property_rental/rentals/tests/test_analytics_portfolio.py`
- Test: `property_rental/rentals/tests/test_analytics_api.py`
- Modify: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/api/analytics.ts`
- Modify: `frontend/src/api/keys.ts`
- Modify: `frontend/src/features/dashboard/filters.ts`
- Modify: `frontend/src/features/dashboard/DashboardFilters.tsx`
- Rename: `frontend/src/features/dashboard/charts/CurrencyExposureChart.tsx` to `frontend/src/features/dashboard/charts/PropertyPortfolioBreakdownChart.tsx`
- Rename: matching test file
- Modify: `frontend/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: dashboard `start`, `end`, `grain`, `currency`, `propertyIds`, and measure.
- Produces: `property_breakdown` time series grouped by stable property IDs for `property_value`, `equity`, `debt`, and `rental_income`.

- [ ] **Step 1: Write failing backend property-breakdown tests**

For two properties and at least three periods, assert series are properties rather than currencies, points follow the requested calendar grain, sold properties disappear after sale, valuation measures carry the latest known snapshot forward, equity is value less debt, rental income contains only transactions in each period, and all values are converted into reporting currency.

```python
assert [series.label for series in result.series] == ["Anokhina", "Wandsworth"]
assert result.measure == "equity"
assert result.points[0]["property_1"] == pytest.approx(300_000)
```

- [ ] **Step 2: Run focused backend tests and verify the currency-grouped contract fails**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py -q -k breakdown`

Expected: FAIL because the current endpoint groups by native currency and does not support equity.

- [ ] **Step 3: Implement the property-grouped time series**

Replace `CurrencyExposureResponse` with `PropertyBreakdownResponse`. Supported measures are:

```python
PROPERTY_BREAKDOWN_MEASURES = {
    "property_value": "Property value",
    "equity": "Equity",
    "debt": "Debt",
    "rental_income": "Rental income",
}
```

Use point keys `property_<id>` and series labels equal to property names. Preserve per-property coverage status so a missing valuation is distinguishable from zero.

- [ ] **Step 4: Rename endpoint and frontend contract**

Expose `GET /api/analytics/portfolio/property-breakdown/`; remove the currency-exposure route, schema, hook, and query-key names in the same commit. Add `equity` to the measure selector.

- [ ] **Step 5: Build the horizontal timeline chart**

Title the card “Portfolio breakdown by property”. Render time on a continuous horizontal X axis and reporting values on Y, with one solid-colored line per property and no dots/dashes. On mobile, keep a minimum 320-pixel plot, wrap the legend, and expose the exact-value table without hover. The measure selector remains in the card header and timeline comes from the global dashboard date/frequency controls.

- [ ] **Step 6: Run backend/frontend tests and commit**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_portfolio.py property_rental/rentals/tests/test_analytics_api.py -q`

Run: `npm test -- --run src/api/analytics.test.tsx src/features/dashboard src/pages/HomePage.test.tsx`

Expected: PASS.

```powershell
git add property_rental/rentals/analytics/portfolio.py property_rental/rentals/api property_rental/rentals/tests/test_analytics_portfolio.py property_rental/rentals/tests/test_analytics_api.py frontend/src/types/analytics.ts frontend/src/api frontend/src/features/dashboard frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.test.tsx
git commit -m "feat: chart portfolio breakdown by property"
```

### Task 7: Fix Property Detail Formatting and Valuation Time Geometry

**Files:**
- Modify: `frontend/src/pages/PropertyDetailPage.tsx`
- Test: `frontend/src/pages/PropertyDetailPage.test.tsx`
- Modify: `frontend/src/features/property/ValuationChart.tsx`
- Test: `frontend/src/features/property/ValuationChart.test.tsx`

**Interfaces:**
- Consumes: property native currency, shared category labels, shared accounting formatter, raw ISO valuation dates.
- Produces: zero-decimal area, friendly recent-transaction categories, and continuous-time valuation chart.

- [ ] **Step 1: Write failing page-format tests**

```tsx
expect(screen.getByText('85 m²')).toBeVisible()
expect(screen.queryByText(/Server-calculated year-to-date/)).not.toBeInTheDocument()
expect(screen.getByText('Cost reimbursement')).toBeVisible()
expect(screen.queryByText('cost_reimbursement')).not.toBeInTheDocument()
```

Use an area fixture of `85.49` to prove zero-decimal rendering.

- [ ] **Step 2: Write a failing sparse-timeline chart test**

Pass records at `2004-01-01`, `2023-01-01`, and `2024-01-01`. Assert X values are epoch milliseconds and the first-to-second gap is approximately nineteen times the second-to-third gap.

```ts
expect((x2023 - x2004) / (x2024 - x2023)).toBeGreaterThan(18)
```

- [ ] **Step 3: Run the tests and verify categorical spacing/current labels fail**

Run: `npm test -- --run src/pages/PropertyDetailPage.test.tsx src/features/property/ValuationChart.test.tsx`

Expected: FAIL.

- [ ] **Step 4: Apply shared formatting**

Render area through `formatNumber(Number(property.area))`, render recent transaction categories through `transactionCategoryLabel`, and all negative monetary values through `formatAccounting`.

- [ ] **Step 5: Use a continuous time X axis**

Precompute `{ ...point, timestamp: parseISO(point.period_start).getTime() }` and configure:

```tsx
<XAxis
  dataKey="timestamp"
  type="number"
  scale="time"
  domain={['dataMin', 'dataMax']}
  tickFormatter={(value) => formatDate(new Date(Number(value)))}
/>
```

Use a `ComposedChart` with numeric X coordinates for every series; preserve missing intervals and do not interpolate synthetic valuation records. Series use the solid palette from Task 2.

- [ ] **Step 6: Run tests and commit**

Run: `npm test -- --run src/pages/PropertyDetailPage.test.tsx src/features/property/ValuationChart.test.tsx`

Expected: PASS.

```powershell
git add frontend/src/pages/PropertyDetailPage.tsx frontend/src/pages/PropertyDetailPage.test.tsx frontend/src/features/property/ValuationChart.tsx frontend/src/features/property/ValuationChart.test.tsx
git commit -m "fix: improve property detail financial presentation"
```

### Task 8: Audit and Correct Tenant Rent Performance in Native Currency

**Files:**
- Modify: `property_rental/rentals/analytics/tenant.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Test: `property_rental/rentals/tests/test_analytics_tenant.py`
- Test: `property_rental/rentals/tests/test_analytics_api.py`
- Modify: `frontend/src/api/analytics.ts`
- Modify: `frontend/src/types/analytics.ts`
- Modify: `frontend/src/pages/TenantDetailPage.tsx`
- Test: `frontend/src/pages/TenantDetailPage.test.tsx`
- Modify: `frontend/src/features/tenant/RentPerformanceChart.tsx`
- Test: `frontend/src/features/tenant/RentPerformanceChart.test.tsx`

**Interfaces:**
- Consumes: tenant lease dates, payday, effective rent history, tenant-linked rent transactions, and property native currency.
- Produces: expected, received, variance, and cumulative arrears in native currency with explicit sign convention.

- [ ] **Step 1: Add calculation characterization tests before changing code**

Cover: lease starting before payday, lease starting after that month's payday, 31st-day payday in February, rent-rate change effective on a due date, rate change after a due date, lease end, payment in the same month but on a different date, late payment, partial payment, overpayment, and an unassigned legacy rent transaction. For the canonical three-month fixture assert:

```python
assert [point["expected"] for point in result.points] == [1_000, 1_200, 1_200]
assert [point["received"] for point in result.points] == [1_000, 1_000, 1_400]
assert [point["variance"] for point in result.points] == [0, -200, 200]
assert [point["cumulative_arrears"] for point in result.points] == [0, -200, 0]
assert result.currency == tenant.property.currency
```

Pin the ownership rule: tenant-linked transactions count; unassigned legacy transactions count only when they fall within this tenant's lease and no overlapping tenant makes attribution ambiguous. This aligns the chart with existing tenant totals without double-counting shared property rent.

- [ ] **Step 2: Run tenant tests and use the failures to identify the incorrect branch**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_tenant.py property_rental/rentals/tests/test_analytics_api.py -q -k rent_performance`

Expected: at least native-currency and legacy-attribution cases fail; retain the observed failing values in the commit notes.

- [ ] **Step 3: Make native currency a backend invariant**

Resolve `currency = tenant.property.currency.upper()` inside `tenant_rent_performance`; reject/return `missing_currency` when absent. Remove reporting-currency selection from this endpoint and convert any differently denominated rent rate/payment into native currency at its due/transaction date.

- [ ] **Step 4: Correct expected and received bucketing without client arithmetic**

Generate one contractual due per eligible month, choose the latest rent record effective on or before that due date, bucket expected by due date and received by transaction date, then derive `variance = received - expected` and cumulative arrears from the opening balance. Keep null values plus explicit issues when currency/FX/rate history is incomplete; never silently substitute zero for unavailable values.

- [ ] **Step 5: Simplify the frontend request and chart**

Remove the currency parameter from tenant-performance query keys and requests. Delete “Server-calculated rent, revenue, and debt. Currency shown in …” from the card. Use solid-colored bars/lines, no patterns/dashes/dots, `formatAccounting` for negative variance/arrears, and show `data.currency` in the card subtitle or axis context as native currency.

- [ ] **Step 6: Run focused suites and commit**

Run: `uv run pytest property_rental/rentals/tests/test_analytics_tenant.py property_rental/rentals/tests/test_analytics_api.py -q`

Run: `npm test -- --run src/pages/TenantDetailPage.test.tsx src/features/tenant/RentPerformanceChart.test.tsx src/api/analytics.test.tsx`

Expected: PASS.

```powershell
git add property_rental/rentals/analytics/tenant.py property_rental/rentals/api/analytics_views.py property_rental/rentals/tests/test_analytics_tenant.py property_rental/rentals/tests/test_analytics_api.py frontend/src/api frontend/src/types/analytics.ts frontend/src/pages/TenantDetailPage.tsx frontend/src/pages/TenantDetailPage.test.tsx frontend/src/features/tenant/RentPerformanceChart.tsx frontend/src/features/tenant/RentPerformanceChart.test.tsx
git commit -m "fix: correct native-currency tenant rent performance"
```

### Task 9: Use Friendly Categories Across Transaction Surfaces

**Files:**
- Modify: `frontend/src/components/forms/TransactionForm.tsx`
- Modify: `frontend/src/pages/TransactionsPage.tsx`
- Test: `frontend/src/pages/TransactionsPage.test.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.tsx`
- Modify: `frontend/src/pages/TenantDetailPage.tsx`

**Interfaces:**
- Consumes: Task 1 `TRANSACTION_CATEGORIES` and `transactionCategoryLabel`.
- Produces: stable raw category values in API/query strings and human labels everywhere visible.

- [ ] **Step 1: Write failing transaction table/filter/dialog tests**

```tsx
expect(await screen.findByText('Cost reimbursement')).toBeVisible()
expect(screen.queryByText('cost_reimbursement')).not.toBeInTheDocument()
await user.click(screen.getByRole('combobox', { name: 'Category' }))
expect(screen.getByRole('option', { name: 'Other expenses' })).toBeVisible()
```

Assert a URL `?category=cost_reimbursement` selects the friendly label while the API hook still receives the raw key. Assert delete-dialog copy also uses the friendly label.

- [ ] **Step 2: Run transaction tests and verify raw-key rendering fails**

Run: `npm test -- --run src/pages/TransactionsPage.test.tsx`

Expected: FAIL.

- [ ] **Step 3: Replace duplicated raw option arrays and visible raw keys**

Derive the form's Zod enum values from the shared registry, map Select items as `<SelectItem value={value}>{label}</SelectItem>`, render table/detail/delete-copy labels through `transactionCategoryLabel`, and keep raw values in requests and URL filters.

- [ ] **Step 4: Make search match both key and friendly label**

```ts
const categoryLabel = transactionCategoryLabel(t.category).toLowerCase()
return comment.includes(q) || t.category.toLowerCase().includes(q) || categoryLabel.includes(q)
```

- [ ] **Step 5: Run tests and commit**

Run: `npm test -- --run src/pages/TransactionsPage.test.tsx src/pages/PropertyDetailPage.test.tsx src/pages/TenantDetailPage.test.tsx`

Expected: PASS.

```powershell
git add frontend/src/components/forms/TransactionForm.tsx frontend/src/pages/TransactionsPage.tsx frontend/src/pages/TransactionsPage.test.tsx frontend/src/pages/PropertyDetailPage.tsx frontend/src/pages/TenantDetailPage.tsx
git commit -m "fix: show friendly transaction category names"
```

### Task 10: Mobile, Contract, and Release Verification

**Files:**
- Modify: `frontend/e2e/investment-dashboard.spec.ts`
- Modify: `frontend/e2e/investment-dashboard-visual.spec.ts`
- Update: snapshots under `frontend/e2e/investment-dashboard-visual.spec.ts-snapshots/`
- Modify if contract changed: `README.md`

**Interfaces:**
- Consumes: completed Tasks 1–9.
- Produces: verified desktop/tablet/mobile release with updated snapshots and documented financial definitions.

- [ ] **Step 1: Add end-to-end acceptance scenarios**

At 390×844, 768×1024, and 1440×1000 verify: collapsed settings; settings expansion; no Properties overlap; non-zero debt/equity fixture values; no `NaN`; yield definition popover; solid revenue/expense lines; restored dashboard P&L; horizontally scrollable annual property P&L; continuous 2004–2023 valuation gap; native-currency tenant chart; friendly transaction categories; accounting parentheses; and no horizontal document overflow.

- [ ] **Step 2: Run all backend quality gates**

Run: `uv lock --check`

Run: `uv run python property_rental/manage.py check`

Run: `uv run pytest -q`

Expected: lock is current, Django reports zero issues, and all tests pass without warnings.

- [ ] **Step 3: Run all frontend quality gates**

Run: `npm run lint`

Run: `npm test -- --run`

Run: `npm run build`

Run: `npx playwright test`

Expected: all commands pass.

- [ ] **Step 4: Review new visual snapshots instead of accepting them blindly**

Inspect desktop, tablet, and mobile screenshots for label collision, chart clipping, insufficient color distinction, misleading interpolation, P&L overflow, inaccessible controls, `NaN`, and currency mismatches. Update snapshots only after the rendered output meets every acceptance criterion.

- [ ] **Step 5: Confirm repository hygiene and commit release verification**

Run: `git diff --check`

Run: `git status --short`

Confirm the unrelated migration remains outside staged changes. If README API descriptions mention currency exposure or net yield, replace them with property breakdown and equity yield definitions.

```powershell
git add frontend/e2e README.md
git commit -m "test: cover financial analytics UX review"
```

## Self-Review

- Spec coverage: all eight dashboard comments, five property comments, two tenant comments, and the transaction-table/filter comment are mapped to Tasks 1–10.
- P&L interpretation: repository history confirms the disappeared component was a per-category, always-visible statement; Task 5 restores it and extends the property view to annual history plus YTD.
- Currency convention: common accounting presentation places the symbol inside the parentheses (`($1,234)`); Task 1 makes that universal.
- Calculation ownership: debt, equity, yields, P&L, and tenant performance remain backend-owned; no React financial recomputation is introduced.
- Mobile coverage: disclosure controls, legends, definition popovers, wide tables, sparse time axes, and all three target widths have explicit tests.
- Placeholder scan: every implementation step contains concrete behavior, commands, and expected results; every cross-task interface is defined.
- Type consistency: `equity_yield`, `property_breakdown`, `ProfitLossResponse`, category helpers, and native tenant currency names remain consistent across backend, serializers, Zod, hooks, and components.
