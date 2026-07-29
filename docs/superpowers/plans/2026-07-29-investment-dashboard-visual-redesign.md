# Investment Performance Dashboard Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy Chart.js-shaped analytics boundary and current chart collection with a typed, investment-performance dashboard that is analytically correct, dense, accessible, and fully functional on mobile.

**Architecture:** Django analytics selectors/services own financial semantics, date bucketing, property scoping, FX conversion, occupancy, yield, and comparison calculations. DRF exposes renderer-neutral typed responses containing raw values and ISO period boundaries; React owns URL filter state, responsive presentation, controlled series visibility, chart/table switching, and drill-down navigation. The old `/chart-data/` endpoint remains during staged migration and is deleted only after every consumer moves.

**Tech Stack:** Python 3.11+, Django 4.2, Django REST Framework, pytest/pytest-django, React 19, TypeScript 6, Vite 8, TanStack Query 5, Recharts 3, shadcn UI, Zod 4, Vitest/Testing Library/MSW, Playwright.

## Global Constraints

- Preserve existing per-user ownership scoping on every analytics query.
- Return raw monetary values with `scale: 1`; display scaling belongs only to frontend formatters.
- Use ISO `YYYY-MM-DD` boundaries in API responses and URL state.
- React must not classify financial categories, convert FX, calculate occupancy, or define yield formulas.
- All chart capabilities must remain available at a 390-pixel viewport without hover or brush-only interaction.
- Every chart must expose loading, error, empty, success, and exact-value table states.
- Positive/negative and series identity must not rely on color alone.
- Preserve the legacy endpoint until its last consumer and characterization test are removed in the same task.
- Do not add drag-and-drop dashboard customization, forecasting, or a second charting library.

---

## Planned File Structure

### Backend

- Create `property_rental/rentals/analytics/contracts.py` — typed dataclasses/enums for metric, grain, series, point, comparison, and summary contracts.
- Create `property_rental/rentals/analytics/filters.py` — parse and validate shared analytics query parameters.
- Create `property_rental/rentals/analytics/cash_flow.py` — portfolio cash-flow, cumulative cash, revenue/expense, and expense-driver calculations.
- Create `property_rental/rentals/analytics/portfolio.py` — summary, contribution, yield, currency exposure, and occupancy calculations.
- Create `property_rental/rentals/analytics/property.py` — raw property valuation history.
- Create `property_rental/rentals/analytics/tenant.py` — expected versus received rent performance.
- Create `property_rental/rentals/api/analytics_serializers.py` — strict nested DRF response serializers and query serializers.
- Create `property_rental/rentals/api/analytics_views.py` — scoped analytics API views.
- Modify `property_rental/rentals/api/urls.py` — mount analytics URLs.
- Create `property_rental/rentals/tests/test_analytics_*.py` — calculation, contract, security, and query tests.

### Frontend

- Create `frontend/src/types/analytics.ts` — runtime-validated analytics contracts.
- Create `frontend/src/api/analytics.ts` — analytics query hooks and normalized query keys.
- Create `frontend/src/features/dashboard/filters.ts` — URL filter schema and serialization.
- Create `frontend/src/features/dashboard/DashboardFilters.tsx` — desktop toolbar and mobile filter sheet.
- Create `frontend/src/components/analytics/AnalyticsChartCard.tsx` — chart state shell.
- Create `frontend/src/components/analytics/ChartLegend.tsx` — controlled accessible legend.
- Create `frontend/src/components/analytics/ChartTooltip.tsx` — shared tooltip content.
- Create `frontend/src/components/analytics/AnalyticsTable.tsx` — responsive exact-value table.
- Create `frontend/src/components/analytics/chartTheme.ts` — explicit palette, stroke, and mark tokens.
- Create `frontend/src/features/dashboard/charts/*.tsx` — dashboard chart compositions.
- Create `frontend/src/features/property/ValuationChart.tsx` — corrected property valuation chart.
- Create `frontend/src/features/tenant/RentPerformanceChart.tsx` — expected/received/variance chart.
- Modify `frontend/src/pages/HomePage.tsx`, `PropertyDetailPage.tsx`, and `TenantDetailPage.tsx` to use the new contracts.
- Modify `frontend/src/App.tsx` for lazy route boundaries.
- Add focused Vitest files alongside each shared component/chart and Playwright scenarios under `frontend/e2e/`.

---

### Task 1: Shared Analytics Contracts and Filter Validation

**Files:**
- Create: `property_rental/rentals/analytics/__init__.py`
- Create: `property_rental/rentals/analytics/contracts.py`
- Create: `property_rental/rentals/analytics/filters.py`
- Create: `property_rental/rentals/api/analytics_serializers.py`
- Test: `property_rental/rentals/tests/test_analytics_contracts.py`

**Interfaces:**
- Produces: `AnalyticsFilters`, `SeriesDefinition`, `TimeSeriesPoint`, `TimeSeriesResponse`, `CategoryValue`, and strict DRF serializers used by all later analytics endpoints.
- `AnalyticsFilters.from_query_params(params, default_currency, effective_date) -> AnalyticsFilters` validates `start`, `end`, `grain`, `currency`, `comparison`, and repeated `property` IDs.

- [ ] **Step 1: Write failing filter and response-contract tests**

```python
def test_filters_reject_end_before_start(rf, landlord):
    request = rf.get('/api/v1/analytics/portfolio/cash-flow/', {
        'start': '2026-07-31', 'end': '2026-01-01', 'grain': 'month'
    })
    with pytest.raises(serializers.ValidationError, match='end must be on or after start'):
        AnalyticsFilters.from_query_params(
            request.GET,
            default_currency=landlord.default_currency,
            effective_date=landlord.effective_date,
        )


def test_time_series_serializer_requires_raw_scale():
    payload = {
        'metric': 'portfolio_cash_flow',
        'grain': 'month',
        'currency': 'USD',
        'scale': 1000,
        'start': '2026-01-01',
        'end': '2026-01-31',
        'series': [],
        'points': [],
    }
    serializer = TimeSeriesResponseSerializer(data=payload)
    assert not serializer.is_valid()
    assert serializer.errors['scale']
```

- [ ] **Step 2: Run the contract tests and verify they fail because the modules do not exist**

Run: `pytest rentals/tests/test_analytics_contracts.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'rentals.analytics'`.

- [ ] **Step 3: Implement contracts and validated filters**

```python
class Grain(StrEnum):
    MONTH = 'month'
    QUARTER = 'quarter'
    YEAR = 'year'


@dataclass(frozen=True)
class AnalyticsFilters:
    start: date
    end: date
    grain: Grain
    currency: str
    comparison: str | None
    property_ids: tuple[int, ...]


@dataclass(frozen=True)
class SeriesDefinition:
    key: str
    label: str
    kind: str


@dataclass(frozen=True)
class TimeSeriesResponse:
    metric: str
    grain: str
    currency: str | None
    scale: int
    start: date
    end: date
    series: tuple[SeriesDefinition, ...]
    points: tuple[dict[str, object], ...]
```

Implement nested serializers with explicit fields. Validate `scale == 1`, ISO dates, supported grains, three-letter currencies, and `start <= end`.

- [ ] **Step 4: Run focused tests**

Run: `pytest rentals/tests/test_analytics_contracts.py -v`

Expected: all contract tests pass.

- [ ] **Step 5: Run existing serializer and chart characterization tests**

Run: `pytest rentals/tests/test_api.py rentals/tests/test_charts_char.py -v`

Expected: existing legacy contracts remain green.

- [ ] **Step 6: Commit the contract boundary**

```bash
git add property_rental/rentals/analytics property_rental/rentals/api/analytics_serializers.py property_rental/rentals/tests/test_analytics_contracts.py
git commit -m "feat: define typed analytics contracts"
```

### Task 2: Portfolio Cash Flow, Trends, and Expense Drivers API

**Files:**
- Create: `property_rental/rentals/analytics/cash_flow.py`
- Create: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Test: `property_rental/rentals/tests/test_analytics_cash_flow.py`
- Test: `property_rental/rentals/tests/test_analytics_api.py`

**Interfaces:**
- Consumes: `AnalyticsFilters` and response contracts from Task 1.
- Produces: `portfolio_cash_flow(user, filters)`, `expense_drivers(user, filters)`, and endpoints `/analytics/portfolio/cash-flow/` and `/analytics/portfolio/expenses/`.

- [ ] **Step 1: Write failing calculation tests for signed cash-flow buckets**

```python
def test_cash_flow_returns_raw_signed_values(landlord, sample_property, transaction_factory):
    transaction_factory(property=sample_property, category='rent', amount=2000, date='2026-01-10')
    transaction_factory(property=sample_property, category='utilities', amount=-300, date='2026-01-12')
    result = portfolio_cash_flow(landlord, filters_for('2026-01-01', '2026-01-31'))
    assert result.scale == 1
    assert result.points == ({
        'period_start': date(2026, 1, 1),
        'period_end': date(2026, 1, 31),
        'rent': 2000.0,
        'utilities': -300.0,
        'total_income': 2000.0,
        'total_expenses': -300.0,
        'net_income': 1700.0,
        'cumulative_net_income': 1700.0,
    },)
```

- [ ] **Step 2: Write failing API ownership and validation tests**

Assert unauthenticated requests fail, property filters cannot expose another landlord's property, invalid dates return 400, and the response contains explicit series kinds.

- [ ] **Step 3: Run focused tests and confirm failures**

Run: `pytest rentals/tests/test_analytics_cash_flow.py rentals/tests/test_analytics_api.py -v`

Expected: imports or endpoint lookup fail.

- [ ] **Step 4: Implement database bucketing and category classification**

Use one scoped transaction queryset, convert values through the existing financial/FX service, and aggregate into calendar month/quarter/year buckets. Define category kind in Python from the canonical constants; do not send category inference to React.

```python
def portfolio_cash_flow(user, filters: AnalyticsFilters) -> TimeSeriesResponse:
    properties = scoped_properties(user, filters.property_ids)
    transactions = Transaction.objects.filter(
        property__in=properties,
        date__range=(filters.start, filters.end),
    ).select_related('property')
    buckets = build_cash_flow_buckets(transactions, filters)
    return TimeSeriesResponse(
        metric='portfolio_cash_flow', grain=filters.grain.value,
        currency=filters.currency, scale=1,
        start=filters.start, end=filters.end,
        series=series_definitions(buckets), points=tuple(buckets),
    )
```

- [ ] **Step 5: Implement strict API views and URL routes**

Use `IsAuthenticated`, build filters from the request user, serialize the dataclass through strict serializers, and return 400 for invalid filters.

- [ ] **Step 6: Run calculation, API, security, and query-count tests**

Run: `pytest rentals/tests/test_analytics_cash_flow.py rentals/tests/test_analytics_api.py rentals/tests/test_security.py -v`

Expected: all pass and the portfolio query count is bounded independently of point count.

- [ ] **Step 7: Commit cash-flow analytics**

```bash
git add property_rental/rentals/analytics/cash_flow.py property_rental/rentals/api/analytics_views.py property_rental/rentals/api/urls.py property_rental/rentals/tests/test_analytics_cash_flow.py property_rental/rentals/tests/test_analytics_api.py
git commit -m "feat: add portfolio cash flow analytics API"
```

### Task 3: Portfolio Summary, Contribution, Yield, Currency, and Occupancy APIs

**Files:**
- Create: `property_rental/rentals/analytics/portfolio.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Test: `property_rental/rentals/tests/test_analytics_portfolio.py`

**Interfaces:**
- Produces: `portfolio_summary`, `property_contribution`, `property_yields`, `currency_exposure`, and `portfolio_occupancy`.
- Currency exposure accepts `measure in {'property_value', 'debt', 'rental_income'}` and always returns one category per native currency.

- [ ] **Step 1: Write failing occupancy-grain tests**

```python
def test_two_overlapping_tenants_in_one_property_count_as_one_occupied_unit(...):
    result = portfolio_occupancy(user, filters_for('2026-01-01', '2026-01-31'))
    point = result.points[0]
    assert point['capacity'] == 1
    assert point['occupied'] == 1
    assert point['vacant'] == 0
    assert point['occupancy_rate'] == 100.0
```

Add cases for never-rented properties, sold properties, gaps between leases, and a property with concurrent tenants.

- [ ] **Step 2: Write failing yield and currency semantic tests**

Assert missing valuations return `status='missing_valuation'`, no denominator is synthesized, raw monetary values are not divided by 1,000, and every requested period retains currency categories.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `pytest rentals/tests/test_analytics_portfolio.py -v`

Expected: module functions are missing.

- [ ] **Step 4: Implement portfolio calculations**

Calculate occupied units as distinct property IDs. Define capacity from owned, unsold properties that have entered rental inventory by the bucket date. Calculate gross and net yield from annualized selected-period revenue/costs divided by the latest valuation at or before `filters.end`.

```python
@dataclass(frozen=True)
class YieldRow:
    property_id: int
    property_name: str
    valuation_date: date | None
    property_value: float | None
    annualized_revenue: float | None
    annualized_costs: float | None
    gross_yield: float | None
    net_yield: float | None
    status: str
```

- [ ] **Step 5: Add strict serializers, views, and routes**

Expose summary, contribution, yields, currency exposure, and occupancy under `/api/v1/analytics/portfolio/`.

- [ ] **Step 6: Run portfolio, FX, financial, and security tests**

Run: `pytest rentals/tests/test_analytics_portfolio.py rentals/tests/test_fx_char.py rentals/tests/test_financials_char.py rentals/tests/test_security.py -v`

Expected: all pass.

- [ ] **Step 7: Commit portfolio analytics**

```bash
git add property_rental/rentals/analytics/portfolio.py property_rental/rentals/api/analytics_views.py property_rental/rentals/api/analytics_serializers.py property_rental/rentals/api/urls.py property_rental/rentals/tests/test_analytics_portfolio.py
git commit -m "feat: add portfolio performance analytics"
```

### Task 4: Property Valuation and Tenant Rent-Performance APIs

**Files:**
- Create: `property_rental/rentals/analytics/property.py`
- Create: `property_rental/rentals/analytics/tenant.py`
- Modify: `property_rental/rentals/api/analytics_views.py`
- Modify: `property_rental/rentals/api/analytics_serializers.py`
- Modify: `property_rental/rentals/api/urls.py`
- Test: `property_rental/rentals/tests/test_analytics_property.py`
- Test: `property_rental/rentals/tests/test_analytics_tenant.py`

**Interfaces:**
- Produces: full-history raw valuation points and expected/received/variance rent points.
- Endpoints: `/analytics/properties/{id}/valuation/` and `/analytics/tenants/{id}/rent-performance/`.

- [ ] **Step 1: Write failing raw-unit and all-history valuation tests**

```python
def test_valuation_returns_full_history_in_raw_currency(...):
    result = property_valuation_history(user, property_id, end=date(2026, 7, 29))
    assert result.scale == 1
    assert result.points[0]['total_value'] == 500000.0
    assert result.points[0]['debt'] == 200000.0
    assert result.points[0]['equity'] == 300000.0
```

- [ ] **Step 2: Write failing expected-versus-received rent tests**

Cover rent-rate changes, partial payments, missing months, payments after vacation, and cumulative arrears.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `pytest rentals/tests/test_analytics_property.py rentals/tests/test_analytics_tenant.py -v`

- [ ] **Step 4: Implement property and tenant selectors**

Use scoped entity lookup. Return exact valuation record dates rather than synthetic monthly repeats. Use lease/rent schedule logic to calculate expected rent and transaction data for received rent.

- [ ] **Step 5: Add API serializers, views, and URLs**

Reject another landlord's entity with 404 and expose explicit `status` when data is insufficient.

- [ ] **Step 6: Run new and existing characterization tests**

Run: `pytest rentals/tests/test_analytics_property.py rentals/tests/test_analytics_tenant.py rentals/tests/test_charts_char.py rentals/tests/test_financials_char.py -v`

Expected: all pass; legacy behavior remains until frontend migration completes.

- [ ] **Step 7: Commit entity analytics**

```bash
git add property_rental/rentals/analytics/property.py property_rental/rentals/analytics/tenant.py property_rental/rentals/api/analytics_views.py property_rental/rentals/api/analytics_serializers.py property_rental/rentals/api/urls.py property_rental/rentals/tests/test_analytics_property.py property_rental/rentals/tests/test_analytics_tenant.py
git commit -m "feat: add property and tenant analytics APIs"
```

### Task 5: Frontend Runtime Contracts, Query Hooks, and URL Filters

**Files:**
- Create: `frontend/src/types/analytics.ts`
- Create: `frontend/src/api/analytics.ts`
- Modify: `frontend/src/api/keys.ts`
- Create: `frontend/src/features/dashboard/filters.ts`
- Test: `frontend/src/api/analytics.test.tsx`
- Test: `frontend/src/features/dashboard/filters.test.ts`

**Interfaces:**
- Produces: Zod schemas and inferred types, `usePortfolioSummary`, `usePortfolioCashFlow`, `useExpenseDrivers`, `usePropertyContribution`, `usePropertyYields`, `useCurrencyExposure`, `usePortfolioOccupancy`, `usePropertyValuationAnalytics`, and `useTenantRentPerformance`.
- Produces: `DashboardFilterState`, `parseDashboardFilters(searchParams, defaults)`, and `serializeDashboardFilters(filters)`.

- [ ] **Step 1: Add Zod and write failing schema tests**

Run: `npm install zod@^4.4.3` only if the locked dependency is not already present.

```ts
it('rejects scaled monetary responses', () => {
  expect(() => timeSeriesSchema.parse({ ...fixture, scale: 1000 })).toThrow()
})

it('accepts raw ISO-bounded time series', () => {
  expect(timeSeriesSchema.parse(fixture).metric).toBe('portfolio_cash_flow')
})
```

- [ ] **Step 2: Write failing URL round-trip tests**

```ts
it('round-trips section, range, currency, grain and properties', () => {
  const parsed = parseDashboardFilters(new URLSearchParams(
    'section=portfolio&start=2026-01-01&end=2026-07-29&currency=GBP&grain=month&property=1&property=3'
  ), defaults)
  expect(serializeDashboardFilters(parsed).toString()).toContain('property=3')
})
```

- [ ] **Step 3: Run tests and verify missing-module failures**

Run: `npm test -- src/api/analytics.test.tsx src/features/dashboard/filters.test.ts`

- [ ] **Step 4: Implement schemas, hooks, keys, and filter serialization**

Validate every response inside `queryFn` before returning it. Normalize property IDs and omit default values only when copied URLs still restore the same view.

- [ ] **Step 5: Run frontend API/filter tests and typecheck**

Run: `npm test -- src/api/analytics.test.tsx src/features/dashboard/filters.test.ts`

Run: `npx tsc -b --pretty false`

Expected: all pass.

- [ ] **Step 6: Commit frontend analytics plumbing**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/types/analytics.ts frontend/src/api/analytics.ts frontend/src/api/analytics.test.tsx frontend/src/api/keys.ts frontend/src/features/dashboard/filters.ts frontend/src/features/dashboard/filters.test.ts
git commit -m "feat: add typed frontend analytics client"
```

### Task 6: Responsive Dashboard Shell and Global Filters

**Files:**
- Create: `frontend/src/features/dashboard/DashboardFilters.tsx`
- Create: `frontend/src/features/dashboard/DashboardSectionNav.tsx`
- Create: `frontend/src/features/dashboard/DashboardLayout.tsx`
- Modify: `frontend/src/pages/HomePage.tsx`
- Test: `frontend/src/features/dashboard/DashboardFilters.test.tsx`
- Test: `frontend/src/pages/HomePage.test.tsx`

**Interfaces:**
- Consumes: filter functions from Task 5.
- Produces: sticky desktop toolbar, mobile bottom-sheet filter surface, and four URL-addressable dashboard sections.

- [ ] **Step 1: Write failing filter interaction tests**

Test desktop controls, mobile "Filters" button, 44-pixel interactive sizing class, URL updates through React Router, reset behavior, and restoration from a copied URL.

- [ ] **Step 2: Run focused UI tests and verify failure**

Run: `npm test -- src/features/dashboard/DashboardFilters.test.tsx src/pages/HomePage.test.tsx`

- [ ] **Step 3: Implement responsive shell and section navigation**

Use the existing shadcn Select/Button/Sheet primitives. Render Overview, Income & Costs, Portfolio, and Risk sections. Keep essential range/currency controls visible on mobile and place property/comparison/grain controls in the sheet.

- [ ] **Step 4: Connect filters to analytics hooks without replacing charts yet**

Render summary data in the KPI row while existing charts remain below as temporary consumers. Do not create a second independent filter state.

- [ ] **Step 5: Run UI tests, lint, and typecheck**

Run: `npm test -- src/features/dashboard/DashboardFilters.test.tsx src/pages/HomePage.test.tsx`

Run: `npm run lint`

Run: `npx tsc -b --pretty false`

- [ ] **Step 6: Commit responsive dashboard structure**

```bash
git add frontend/src/features/dashboard frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.test.tsx
git commit -m "feat: add responsive investment dashboard shell"
```

### Task 7: Shared Accessible Analytics Components

**Files:**
- Create: `frontend/src/components/analytics/AnalyticsChartCard.tsx`
- Create: `frontend/src/components/analytics/ChartLegend.tsx`
- Create: `frontend/src/components/analytics/ChartTooltip.tsx`
- Create: `frontend/src/components/analytics/AnalyticsTable.tsx`
- Create: `frontend/src/components/analytics/chartTheme.ts`
- Create: `frontend/src/components/analytics/AnalyticsChartCard.test.tsx`
- Create: `frontend/src/components/analytics/ChartLegend.test.tsx`
- Create: `frontend/src/components/analytics/AnalyticsTable.test.tsx`

**Interfaces:**
- Produces: `AnalyticsChartCard({state, title, subtitle, controls, summary, table, children})`, `ChartLegend({series, hiddenKeys, onToggle})`, and responsive table/tooltip primitives.

- [ ] **Step 1: Write failing state-shell tests**

Assert loading shows a fixed-footprint skeleton, error exposes Retry, empty shows metric-specific copy/action, success can toggle chart/table, and failed data never renders the empty state.

- [ ] **Step 2: Write failing legend and table accessibility tests**

Assert legend controls are buttons with `aria-pressed`, keyboard activation changes hidden keys, numeric cells are right-aligned, and the first column is sticky in the overflow container.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `npm test -- src/components/analytics`

- [ ] **Step 4: Implement shared components and restrained theme**

Use blue/gold/slate roots, explicit category maps, consistent strokes, tabular numeral classes, visible focus, `prefers-reduced-motion`, and no gradients in marks.

- [ ] **Step 5: Run component tests and axe-compatible semantic checks**

Run: `npm test -- src/components/analytics`

Expected: loading/error/empty/success, keyboard legend, and table tests pass.

- [ ] **Step 6: Commit shared analytics UI**

```bash
git add frontend/src/components/analytics
git commit -m "feat: add accessible analytics chart primitives"
```

### Task 8: Overview and Income & Costs Charts

**Files:**
- Create: `frontend/src/features/dashboard/charts/NetCashFlowChart.tsx`
- Create: `frontend/src/features/dashboard/charts/CumulativeCashChart.tsx`
- Create: `frontend/src/features/dashboard/charts/RevenueExpenseTrendChart.tsx`
- Create: `frontend/src/features/dashboard/charts/ExpenseDriversChart.tsx`
- Create tests beside each chart.
- Modify: `frontend/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: typed analytics responses and shared chart primitives.
- Produces: Overview and Income & Costs sections with exact-value tables and transaction drill-down.

- [ ] **Step 1: Write failing semantic chart tests**

Test signed cash-flow geometry inputs, zero-line presence, cumulative final label, ranked expenses, long labels, hidden-series behavior, and exact-value table content. Test with at least 12 periods and a sparse three-period fixture.

- [ ] **Step 2: Write failing drill-down tests**

Assert pointer and keyboard activation navigate to `/transactions` with exact `from`, `to`, `category`, `currency`, and selected property query parameters.

- [ ] **Step 3: Run chart tests and verify failure**

Run: `npm test -- src/features/dashboard/charts`

- [ ] **Step 4: Implement the four chart components**

Use Recharts only for marks/axes. Use controlled legend state, explicit period controls, direct final labels, shared tooltip/table components, and bars rather than a donut for expense drivers.

- [ ] **Step 5: Replace legacy Overview/Income charts in HomePage**

Remove `CashFlowChart`, `NetIncomeTrendChart`, and `ExpenseBreakdownChart` imports from HomePage after their replacements are rendered and tested.

- [ ] **Step 6: Run focused tests, full frontend tests, and build**

Run: `npm test -- src/features/dashboard/charts src/pages/HomePage.test.tsx`

Run: `npm test`

Run: `npm run build`

- [ ] **Step 7: Commit cash-flow visual redesign**

```bash
git add frontend/src/features/dashboard/charts frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.test.tsx
git commit -m "feat: redesign portfolio cash flow visuals"
```

### Task 9: Portfolio and Risk Charts

**Files:**
- Create: `frontend/src/features/dashboard/charts/PropertyContributionChart.tsx`
- Create: `frontend/src/features/dashboard/charts/YieldComparisonChart.tsx`
- Create: `frontend/src/features/dashboard/charts/CurrencyExposureChart.tsx`
- Create: `frontend/src/features/dashboard/charts/OccupancyRiskChart.tsx`
- Create tests beside each chart.
- Modify: `frontend/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: Task 3 endpoints and Tasks 5/7 frontend contracts/components.
- Produces: Portfolio and Risk dashboard sections.

- [ ] **Step 1: Write failing correctness-facing component tests**

Assert property contribution preserves negative contributors, yield rows expose missing valuations without plotting a fabricated point, currency exposure retains one bar per currency for every period, and occupancy never renders above 100%.

- [ ] **Step 2: Write failing mobile interaction tests**

At a mocked 390-pixel viewport, verify explicit range controls, exposure-measure selection, wrapping/compact legends, touch-sized controls, and table access without hover.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `npm test -- src/features/dashboard/charts/PropertyContributionChart.test.tsx src/features/dashboard/charts/YieldComparisonChart.test.tsx src/features/dashboard/charts/CurrencyExposureChart.test.tsx src/features/dashboard/charts/OccupancyRiskChart.test.tsx`

- [ ] **Step 4: Implement Portfolio and Risk charts**

Use horizontal bars for contribution/currency, a two-dot-per-property yield comparison with average reference, and a stepped occupancy-rate line with vacant/capacity context.

- [ ] **Step 5: Replace legacy currency and occupancy charts in HomePage**

Remove `CurrencyExposureChart` and `OccupancyChart` legacy imports after the new charts pass tests.

- [ ] **Step 6: Run focused/full tests and production build**

Run: `npm test`

Run: `npm run build`

Expected: all tests pass and no chart uses client-side occupancy or exposure aggregation.

- [ ] **Step 7: Commit Portfolio and Risk visuals**

```bash
git add frontend/src/features/dashboard/charts frontend/src/pages/HomePage.tsx frontend/src/pages/HomePage.test.tsx
git commit -m "feat: add portfolio and risk analytics visuals"
```

### Task 10: Property Valuation and Tenant Rent-Performance Views

**Files:**
- Create: `frontend/src/features/property/ValuationChart.tsx`
- Create: `frontend/src/features/property/ValuationChart.test.tsx`
- Create: `frontend/src/features/tenant/RentPerformanceChart.tsx`
- Create: `frontend/src/features/tenant/RentPerformanceChart.test.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.tsx`
- Modify: `frontend/src/pages/PropertyDetailPage.test.tsx`
- Modify: `frontend/src/pages/TenantDetailPage.tsx`
- Modify: `frontend/src/pages/TenantDetailPage.test.tsx`

**Interfaces:**
- Consumes: raw valuation and rent-performance endpoints from Task 4.
- Produces: accurate all-history valuation and expected/received rent views.

- [ ] **Step 1: Write failing valuation-unit and navigation tests**

Assert a raw `500000` GBP value formats as £500k on the axis and £500,000 in the tooltip/table, "All time" includes the earliest fixture valuation, and the action navigates to valuation history rather than transactions.

- [ ] **Step 2: Write failing tenant performance tests**

Assert expected line, received bars, signed variance, cumulative arrears, explicit date range, and exact table values.

- [ ] **Step 3: Run focused tests and verify failure**

Run: `npm test -- src/features/property src/features/tenant src/pages/PropertyDetailPage.test.tsx src/pages/TenantDetailPage.test.tsx`

- [ ] **Step 4: Implement and integrate both detail charts**

Delete the five-year client-side cutoff assumption. Use server-provided full valuation records and rent-performance points.

- [ ] **Step 5: Run focused/full frontend tests and build**

Run: `npm test`

Run: `npm run build`

- [ ] **Step 6: Commit entity chart redesign**

```bash
git add frontend/src/features/property frontend/src/features/tenant frontend/src/pages/PropertyDetailPage.tsx frontend/src/pages/PropertyDetailPage.test.tsx frontend/src/pages/TenantDetailPage.tsx frontend/src/pages/TenantDetailPage.test.tsx
git commit -m "feat: redesign property and tenant performance charts"
```

### Task 11: Remove Legacy Chart Contract and Components

**Files:**
- Delete: `property_rental/rentals/services/charts.py`
- Modify: `property_rental/rentals/api/views.py`
- Modify: `property_rental/rentals/api/urls.py`
- Modify: `property_rental/rentals/api/serializers.py`
- Delete: `property_rental/rentals/tests/test_charts_char.py`
- Modify: `property_rental/rentals/tests/test_api.py`
- Delete: `frontend/src/api/charts.ts`
- Delete legacy files under `frontend/src/components/charts/` after confirming no imports.
- Modify: `frontend/src/api/keys.ts`

**Interfaces:**
- Removes: `/api/v1/chart-data/`, `ChartDataResponseSerializer`, `useChartData`, `transformForRecharts`, and all legacy chart components.
- Preserves: all new `/api/v1/analytics/` endpoints.

- [ ] **Step 1: Prove there are no remaining legacy consumers**

Run: `rg -n "chart-data|useChartData|ChartDataResponse|transformForRecharts|components/charts" frontend/src property_rental/rentals`

Expected: matches exist only in files scheduled for deletion and legacy tests/docs.

- [ ] **Step 2: Write/update endpoint tests asserting the old route is absent**

```python
def test_legacy_chart_data_route_is_removed(auth_client):
    response = auth_client.get('/api/v1/chart-data/')
    assert response.status_code == 404
```

- [ ] **Step 3: Delete legacy backend and frontend chart code**

Remove URL/view/serializer imports in the same change. Keep historical specs and plans unchanged.

- [ ] **Step 4: Run backend and frontend suites**

Run: `pytest -q`

Run: `npm test`

Run: `npm run build`

Expected: all pass with no source-code match for legacy chart interfaces.

- [ ] **Step 5: Commit legacy removal**

```bash
git add -A property_rental/rentals frontend/src
git commit -m "refactor: remove legacy chart data contract"
```

### Task 12: End-to-End Responsive QA, Accessibility, and Code Splitting

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/e2e/investment-dashboard.spec.ts`
- Create: `frontend/e2e/investment-dashboard-visual.spec.ts`
- Modify: `.github/workflows/ci.yml`
- Modify: `frontend/vite.config.ts` only if explicit chunk grouping is needed after route lazy loading.
- Modify: `README.md` with analytics endpoint and local visual-test commands.

**Interfaces:**
- Produces: lazy route boundaries, desktop/tablet/mobile E2E coverage, visual snapshots, and CI gates.

- [ ] **Step 1: Add failing Playwright scenarios**

Cover 1440, 768, and 390 pixel widths; URL filter restoration; mobile filter sheet; chart/table toggle; keyboard legend; transaction drill-down; valuation navigation; loading/error/empty states; and long-label/negative/mixed-currency fixtures.

- [ ] **Step 2: Run Playwright and record the expected failures**

Run the repository's Playwright command after starting the documented Django/Vite test stack.

Expected: lazy loading/snapshot assertions fail before final integration adjustments.

- [ ] **Step 3: Add route-level lazy loading**

```tsx
const HomePage = lazy(() => import('@/pages/HomePage'))
const PropertiesPage = lazy(() => import('@/pages/PropertiesPage'))
const PropertyDetailPage = lazy(() => import('@/pages/PropertyDetailPage'))
```

Wrap route elements in a consistent `Suspense` fallback. Keep authentication/session initialization outside route chunks.

- [ ] **Step 4: Fix responsive and accessibility issues surfaced by E2E inspection**

Limit changes to failures demonstrated by the scenarios: clipping, inaccessible controls, hover-only information, incorrect focus order, illegible legends, or table overflow.

- [ ] **Step 5: Run complete verification**

Backend:

```bash
pytest -q
python manage.py check
```

Frontend:

```bash
npm run lint
npm test
npm run build
```

E2E: run all investment-dashboard Playwright scenarios at the three required viewport widths.

Expected: all commands pass; the initial production bundle no longer produces the current monolithic main-chunk warning.

- [ ] **Step 6: Inspect production output and snapshots**

Record initial JS chunk and dashboard route chunk sizes in the commit message or PR notes. Review desktop, tablet, and mobile snapshots for label clipping, inconsistent plot heights, tooltip overflow, and touch target sizing.

- [ ] **Step 7: Commit final QA and performance work**

```bash
git add frontend/src/App.tsx frontend/e2e .github/workflows/ci.yml frontend/vite.config.ts README.md
git commit -m "test: verify responsive investment dashboard"
```

---

## Final Release Verification

- [ ] Run `git status --short` and confirm only intentional files are changed.
- [ ] Run the complete backend suite in the configured project environment.
- [ ] Run frontend lint, all Vitest tests, TypeScript build, and Vite production build.
- [ ] Run Playwright at 1440, 768, and 390 pixels.
- [ ] Confirm raw valuation values agree between API, tooltip, and table.
- [ ] Confirm occupancy never exceeds 100% for overlapping-tenant fixtures.
- [ ] Confirm every currency-exposure period retains its native-currency breakdown.
- [ ] Confirm copied dashboard URLs restore section, range, comparison, currency, frequency, and property selection.
- [ ] Confirm every chart exposes retry, metric-specific empty guidance, table view, keyboard legend, and touch-accessible controls.
- [ ] Confirm `/api/v1/chart-data/` returns 404 and no application source imports the legacy adapter.
- [ ] Confirm the production build is route-split and does not emit the current monolithic main-chunk warning.
