# Investment Performance Dashboard Visual Redesign

**Date:** 2026-07-29
**Status:** Approved in design review
**Scope:** Analytics contracts, dashboard information architecture, chart redesign, responsive UX, accessibility, and chart QA

## 1. Context

The application has been modernized from Django templates, Bootstrap, jQuery, and Chart.js into a React and TypeScript SPA backed by Django REST Framework. The strategic stack is sound, but the chart layer still consumes a legacy Chart.js-shaped response containing parallel `labels` and `datasets` arrays. Several investment metrics are reconstructed or interpreted in React, and known legacy quirks remain embedded in the backend service.

The current implementation also has correctness and UX risks:

- Property valuation values are divided by 1,000 by the backend while the frontend can label them as unscaled currency.
- Occupancy counts active tenants but compares them with property capacity.
- Currency exposure changes meaning for some selected periods.
- An "All time" valuation view is limited by a five-year parent query.
- Chart loading, error, and empty states are inconsistent.
- Legend toggling, brushing, drill-down, accessibility, and chart semantics lack dedicated tests.
- The production JavaScript bundle is large and has no route-level code splitting.

The redesign will make the dashboard a dense investment-performance workspace that remains fully functional on mobile. It is not primarily an operational property-management cockpit, although material investment risks such as vacancy, lease concentration, and currency exposure remain visible.

## 2. Goals

1. Make portfolio return, valuation, income, costs, yield, leverage, and risk immediately understandable.
2. Preserve analytical depth on desktop and mobile without hiding essential functionality.
3. Move financial metric definitions, date bucketing, category classification, and FX conversion into typed backend analytics services.
4. Replace legacy chart payloads with renderer-neutral contracts containing raw values and explicit metadata.
5. Make every chart usable with mouse, keyboard, and touch, with an exact-value table alternative.
6. Make filters shareable through URL state and consistent across dashboard sections.
7. Add calculation, component, accessibility, interaction, responsive, and visual-regression coverage.
8. Reduce initial frontend bundle weight through route-level code splitting.

## 3. Non-Goals

- User-configurable drag-and-drop dashboard layouts.
- A mobile-native application.
- Real-time streaming analytics.
- Predictive valuation, forecasting, or scenario modeling.
- Replacing Django, DRF, React, TanStack Query, shadcn, or Recharts.
- Redesigning unrelated entity forms and CRUD workflows.

## 4. Chosen Product Direction

The dashboard is a responsive analytical workbench rather than a continuous unstructured page or configurable widget canvas.

It has four analytical sections:

1. **Overview** — portfolio value, leverage, returns, headline cash flow, and performance summary.
2. **Income & Costs** — revenue, expenses, net income, cumulative cash generation, and detailed P&L.
3. **Portfolio** — property contribution, yield comparison, valuation, and leverage.
4. **Risk** — vacancy, lease concentration, and currency exposure.

A sticky global filter bar controls:

- as-of date;
- reporting period and comparison period;
- reporting currency;
- frequency;
- selected properties.

Filters are encoded in URL query parameters. A copied dashboard URL must restore the same section, filters, and comparison context.

## 5. Responsive Information Architecture

### 5.1 Desktop

- Use a 12-column grid.
- Headline charts span 12 columns.
- Comparable secondary charts use aligned 6-column cards.
- Dense comparison charts can use 8/4 or 7/5 layouts when one chart is materially more important.
- Cards in a row align at their top edge; chart plot regions use consistent heights.
- The filter bar remains visible while scrolling without obscuring the page title or chart controls.

### 5.2 Mobile

- Preserve all metrics, filters, tables, comparisons, and drill-down actions.
- Stack cards into a single column with a minimum useful plot height of 280 pixels.
- Keep essential filters visible; open advanced filters in a bottom sheet.
- Use explicit range selectors and next/previous controls instead of requiring brush gestures.
- Use 44-pixel minimum touch targets.
- Allow wide financial tables to scroll horizontally while keeping the first column sticky.
- Move legends into wrapping button groups or a compact series menu when horizontal space is insufficient.
- Never require hover to reveal essential values or actions.

## 6. Visual Design System

### 6.1 Foundation

- Near-white application canvas and white cards.
- Quiet neutral borders and grid lines.
- Dark charcoal primary text and slate secondary text.
- Tabular numerals for KPIs, axes, tooltips, and financial tables.
- Approximately 16–20 pixels of card padding and consistent card radii.
- Avoid decorative gradients in chart marks.

### 6.2 Palette

- Primary blue: selected or focal series.
- Warm gold: comparison or secondary investment series.
- Slate: benchmarks, totals, and context.
- Additional category colors are capped and explicitly mapped.
- Positive and negative meaning must not rely on green and red alone. Use signed labels, zero lines, tone, fill style, and direct annotation.
- Series that overlap must remain distinguishable in grayscale through line style, markers, open fills, or direct labels.

### 6.3 Chart Typography and Context

- Titles are descriptive, not promotional.
- Subtitles state currency, date range, frequency, filters, and denominator when relevant.
- Tooltips use a shared structure: period, primary value, comparison value, variance, and property or portfolio context.
- Axis labels use compact display formatting only. Raw API values are never pre-scaled.
- Table views use full currency and percentage formatting and right-align numeric columns.

### 6.4 KPI Cards

Each primary KPI can show:

- current value;
- absolute change;
- percentage change;
- comparison-period label;
- a sparkline only when at least eight meaningful temporal observations are available.

Primary Overview KPIs are portfolio value, debt, equity, net yield, total return, and net income. Count-style operational KPIs are secondary unless they materially explain investment performance.

## 7. Chart Portfolio

### 7.1 Net Cash Flow

**Question:** How did income and cost components produce portfolio net cash flow over time?

- Diverging stacked columns.
- Income is above zero; expenses are below zero.
- Prominent zero line.
- Net-income overlay or directly labeled net marker.
- Period/category activation opens Transactions with matching URL filters.
- Table contains period, every component, total income, total expenses, and net income.

### 7.2 Cumulative Cash Generation

**Question:** How much cumulative cash has the portfolio generated over the selected horizon?

- Single line with optional comparison-period line.
- Start-of-window value is explicitly defined.
- Direct label on the final value.
- No area gradient.

### 7.3 Revenue and Expense Trend

**Question:** Are income and operating costs moving favorably?

- Two-series line or grouped columns depending on frequency and number of observations.
- Previous-period comparison is optional and visually subordinate.
- Net margin appears in the tooltip/table, not as an unrelated third axis.

### 7.4 Expense Drivers

**Question:** Which categories drive portfolio costs and how have they changed?

- Ranked horizontal bars.
- Current-period value, prior-period reference, and signed variance.
- Long category labels remain fully visible.
- Replaces the donut chart because exact ranking and comparison matter more than rough part-to-whole perception.

### 7.5 Property Contribution

**Question:** Which properties contribute most to portfolio net income?

- Sorted horizontal bars.
- One row per property.
- Tooltip and table include value, share of portfolio net income, revenue, and expenses.
- Negative contributors remain visible below zero.

### 7.6 Yield Comparison

**Question:** How do gross and net yield compare across properties?

- Property-level dot plot with gross and net yield points.
- Portfolio-average reference line.
- Sorted by net yield by default.
- Tooltip includes valuation date, property value, annualized revenue, annualized costs, gross yield, and net yield.
- Missing or stale valuations are explicit states, never coerced into a synthetic denominator.

### 7.7 Valuation and Leverage

**Question:** How have a property's value and capital structure changed?

- Stacked Debt and Equity columns.
- Total property value line.
- Raw currency values from the backend; compact scaling belongs solely to the renderer.
- "All time" queries the full valuation history.
- Valuation changes navigate to valuation records, not transactions. Transaction drill-down is not attached to valuation marks.

### 7.8 Currency Exposure

**Question:** How much of the selected measure is associated with each native property currency?

- Horizontal bars grouped by native property currency and expressed in reporting currency.
- User selects a supported measure: property value, debt, or rental income.
- Title names the selected measure, for example "Property value by native currency."
- Every period option preserves the currency dimension.
- This chart must not be called value at risk because no probabilistic loss model is calculated.

### 7.9 Occupancy Risk

**Question:** How has investable rental capacity been utilized?

- Backend calculates distinct active properties and distinct occupied properties per period.
- Stepped occupancy-rate line with vacant-unit count in tooltip/table.
- Capacity policy explicitly handles properties before first rental, after sale, and during excluded periods.
- Multiple tenants on one property cannot produce occupancy above 100%.

### 7.10 Tenant Rent Performance

**Question:** Was expected rent received on schedule?

- Received-rent bars.
- Expected-rent reference line.
- Signed variance and cumulative arrears in tooltip/table.
- Explicit range selectors on every device; desktop brush is optional secondary navigation.

## 8. Interaction Model

### 8.1 Global Filters

Dashboard filters are parsed from and serialized to URL query parameters. Defaults come from the authenticated user's settings only when the URL does not specify a value.

Changing a global filter updates all compatible charts. A chart-specific control is allowed only when the concept does not apply globally, such as selecting the exposure measure.

### 8.2 Series Visibility

- Legend items are real buttons with `aria-pressed` state.
- Hidden series are controlled React state, not an assumed Recharts default.
- Series visibility remains understandable without color.
- The table view indicates hidden chart series without deleting their data.

### 8.3 Drill-Down

- Interactive chart marks are keyboard focusable or paired with an explicit "View transactions" action.
- Drill-down URLs include exact start/end dates, category, property, tenant, and currency context when applicable.
- Valuation charts drill into valuation history rather than transactions.
- Hover is never the sole means of discovering drill-down behavior.

### 8.4 Range Selection

- Preset ranges are always available.
- Custom dates are available through the filter surface.
- Desktop brushes may refine the visible range but synchronize with explicit state.
- Mobile does not require precise drag gestures.

## 9. Analytics Architecture

### 9.1 Backend Responsibilities

Django analytics services own:

- date validation and bucketing;
- property/tenant ownership scoping;
- financial category classification;
- FX conversion;
- occupancy and capacity definitions;
- yield and return formulas;
- current/comparison-period calculations;
- renderer-neutral response construction.

Proposed endpoints:

- `GET /api/v1/analytics/portfolio/summary/`
- `GET /api/v1/analytics/portfolio/cash-flow/`
- `GET /api/v1/analytics/portfolio/expenses/`
- `GET /api/v1/analytics/portfolio/property-contribution/`
- `GET /api/v1/analytics/portfolio/yields/`
- `GET /api/v1/analytics/portfolio/currency-exposure/`
- `GET /api/v1/analytics/portfolio/occupancy/`
- `GET /api/v1/analytics/properties/{id}/valuation/`
- `GET /api/v1/analytics/tenants/{id}/rent-performance/`

The existing `/chart-data/` endpoint remains temporarily for unmigrated consumers and is removed after all chart consumers move.

### 9.2 Renderer-Neutral Contract

Time-series responses use ISO period boundaries and raw numeric values:

```json
{
  "metric": "portfolio_cash_flow",
  "grain": "month",
  "currency": "USD",
  "scale": 1,
  "start": "2026-01-01",
  "end": "2026-07-31",
  "series": [
    {"key": "rent", "label": "Rent", "kind": "income"},
    {"key": "utilities", "label": "Utilities", "kind": "expense"}
  ],
  "points": [
    {
      "period_start": "2026-01-01",
      "period_end": "2026-01-31",
      "rent": 1200.0,
      "utilities": -150.0
    }
  ]
}
```

Comparison and category endpoints follow the same principles: stable keys, human labels, raw values, explicit units, and sufficient denominator/context fields. DRF serializers validate nested structures rather than accepting arbitrary dictionaries.

### 9.3 Frontend Responsibilities

React owns:

- URL and local presentation state;
- query orchestration and caching;
- chart/table switching;
- responsive layout;
- controlled legends;
- keyboard, pointer, and touch interaction;
- rendering and display-scale selection;
- navigation to filtered detail views.

React must not reclassify transaction categories, reconstruct occupancy, perform FX conversion, or define yield formulas.

### 9.4 Shared Frontend Units

- `DashboardFilters` — URL-synchronized global filter model.
- `AnalyticsChartCard` — title, subtitle, state handling, controls, chart/table toggle, and accessible summary.
- `ChartLegend` — controlled, keyboard-accessible series visibility.
- `ChartTooltip` — shared value/comparison/variance formatting.
- `ChartEmptyState` and `ChartErrorState` — consistent recovery and data-entry guidance.
- `AnalyticsTable` — exact-value alternative with sticky labels and responsive overflow.
- Chart-specific components contain only visual composition and chart-specific interactions.

## 10. Loading, Error, and Empty States

Every chart renders exactly one explicit state:

1. **Loading** — skeleton that approximates the final chart footprint.
2. **Error** — concise message, retry action, and preserved filters.
3. **Empty** — metric-specific explanation and relevant action.
4. **Success** — chart and table using validated data.

A failed query must never be represented as an empty successful chart. Missing valuation, missing FX, and no transactions are distinct conditions with different messages.

## 11. Accessibility

- All controls have programmatic labels.
- Legend buttons expose pressed state.
- Chart drill-down has a keyboard path.
- Focus indicators remain visible.
- Touch targets are at least 44 by 44 pixels.
- Table alternatives expose exact values and semantic headers.
- Color is never the sole carrier of category, sign, selection, or comparison.
- Essential information is not hover-only.
- Motion respects `prefers-reduced-motion`.
- Charts include a concise accessible summary describing metric, date range, currency, and primary comparison.

## 12. Testing and QA

### 12.1 Backend

- Unit tests for every metric definition and boundary condition.
- Contract tests for each analytics serializer and endpoint.
- Cross-user ownership tests.
- FX conversion tests with direct and multi-hop rates.
- Occupancy tests for overlapping leases, multiple tenants per property, sale dates, and never-rented properties.
- Yield tests for missing/stale valuations and zero denominators.
- Query-count or performance tests for portfolio-sized fixture data.

### 12.2 Frontend

- Runtime response validation before rendering.
- Component tests for chart semantics, formatters, empty/error/loading states, controlled legends, and table views.
- Interaction tests for keyboard and pointer drill-down.
- URL-state tests for global filters and copied-view restoration.
- Mobile tests for filter sheets, legend controls, range selection, and horizontal tables.

### 12.3 End-to-End and Visual QA

Playwright covers:

- desktop width at 1440 pixels;
- tablet width at 768 pixels;
- mobile width at 390 pixels;
- filter persistence and URL restoration;
- transaction drill-down;
- valuation-history navigation;
- chart/table switching;
- loading, empty, and error states;
- light and dark themes if dark theme remains a supported product feature.

Visual regression fixtures include long property/category names, negative values, mixed currencies, sparse data, and dense multi-year data.

## 13. Performance

- Route-level lazy loading separates dashboard, entity, and authentication routes.
- Chart libraries are loaded only for routes that render charts.
- Analytics endpoints aggregate on the server and avoid per-point database loops.
- Queries use stable TanStack Query keys derived from normalized filters.
- Large table views paginate or virtualize when necessary.
- Production build records initial and route chunk sizes; the initial bundle must no longer trigger the current monolithic-chunk warning.

## 14. Delivery Sequence

1. Introduce shared metric definitions and typed analytics contracts.
2. Fix valuation units, occupancy grain, all-time valuation range, and currency-exposure semantics.
3. Build the responsive dashboard shell and URL-synchronized filters.
4. Introduce shared chart card, legend, tooltip, state, and table primitives.
5. Replace Overview and Income & Costs charts.
6. Replace Portfolio and Risk charts.
7. Upgrade property valuation and tenant rent-performance views.
8. Remove the legacy chart-data adapter and endpoint after all consumers migrate.
9. Add full responsive, accessibility, interaction, contract, and visual-regression coverage.
10. Add route-level code splitting and verify production performance.

## 15. Definition of Done

1. The dashboard implements the four-section responsive analytical workbench.
2. Every analytical control and chart capability is available on mobile without requiring hover or brush gestures.
3. All chart values use raw backend units with explicit currency and scale metadata.
4. Occupancy cannot exceed 100% and is calculated at distinct-property grain.
5. Every currency-exposure period retains its currency breakdown and names the exposure measure accurately.
6. "All time" valuation includes the complete available valuation history.
7. Backend services own financial semantics; React owns display and interaction only.
8. Every chart has loading, error, empty, success, and exact-value table states.
9. Legend and drill-down interactions are keyboard and touch accessible.
10. Backend, frontend, Playwright, accessibility, responsive, and production-build checks pass.
11. The old Chart.js-shaped adapter and `/chart-data/` endpoint are removed after consumer migration.
12. The initial production JavaScript bundle is route-split and no longer produces the current monolithic-chunk warning.

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Metric outputs change during contract migration | Preserve calculation characterization tests, then add explicit metric-definition tests before changing consumers. |
| Dashboard scope becomes a big-bang rewrite | Migrate section by section while retaining the legacy endpoint for unmigrated consumers. |
| Dense mobile UI becomes unusable | Test at 390 pixels from the first shared component and use explicit compact controls rather than desktop gestures. |
| Backend aggregation becomes slow | Add query-count tests, grouped database aggregation, and caching only after measurement. |
| New visual system overuses color | Enforce explicit palette maps and non-color distinction in shared chart primitives. |
| Comparison periods become ambiguous | Include exact current/comparison boundaries in every analytics response and tooltip. |

## 17. Decisions Closed

- Primary product purpose: investment performance.
- Workspace density: analytical rather than executive-summary-only.
- Mobile: full feature parity, not a simplified read-only view.
- Layout: responsive analytical workbench with four sections.
- Chart payloads: renderer-neutral, typed, raw-value contracts.
- Donut expense chart: replaced with ranked horizontal bars.
- Occupancy calculation: distinct property grain on the backend.
- Currency chart terminology: name the selected measure; do not call it value at risk.
- Brushes: optional desktop enhancement, never the only range control.
- Configurable drag-and-drop widgets: out of scope.
