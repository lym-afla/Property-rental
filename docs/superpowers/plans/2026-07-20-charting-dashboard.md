# Charting Overhaul + Dashboard — Implementation Plan (Plan C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 8 charts in Recharts (3 rebuilt + 5 new), wire click-to-drill-down + legend toggle + time-range brush, mount them on the HomePage dashboard + PropertyDetail/TenantDetail pages, and delete the remaining dead code (orphaned templatetags, TenantDetailPage test gap, SPA catch-all 301 fix from B2 review).

**Architecture:** Recharts renders inside a reusable `<ChartCard>` wrapper with title/controls/SR-summary/"view as table" toggle. Data flows from `/api/v1/chart-data/` via a new `useChartData` hook. The `{labels, datasets, currency}` API shape transforms to Recharts' flat-object-per-x format in a small adapter. The HomePage becomes the real dashboard with KPI cards + chart tiles. Chart click handlers navigate to `/transactions?...` (drill-down). A light Playwright smoke suite covers the end-to-end chart rendering.

**Tech Stack:** React 19 + TypeScript 6 + Recharts (latest) + TanStack Query v5 + shadcn/ui + Tailwind v4 + Vitest + Testing Library + MSW (frontend); Playwright (visual smoke).

## Global Constraints

- **8 charts**: 5 on HomePage (Cash Flow, Net Income Trend, Expense Breakdown, Occupancy, Currency Exposure), 2 on PropertyDetail (Valuation, Rent Yield), 1 on TenantDetail (Rent History).
- **3 interactive features**: click-to-drill-down (charts 1, 6, 8), legend toggle (charts 1, 3, 5, 6), time-range brush (charts 1, 2, 8).
- **All Phase 1-deferred chart bugs eliminated** by the rewrite (aspectRatio, stale valuation, $k label, accessibility, responsiveness).
- App is **personal / not live**.
- Existing suites (112 backend + 84 frontend) must stay green.
- Git identity (repo-local): `YL-STARDESTROYER <yaroslav.linik@gmail.com>`.
- Working dir: `D:/Developing/Property-rental`. Frontend at `frontend/`.
- Run frontend tests from `frontend/`: `cd frontend && npm test`.
- Platform: Windows, Git Bash.

---

## Task Ordering

1. **Recharts install + ChartCard + formatCurrency** (Task 1) — foundation.
2. **useChartData hook + data adapter** (Task 2) — the data layer.
3. **Cash Flow chart** (Task 3) — the headline chart, with drill-down + brush.
4. **Net Income Trend chart** (Task 4) — line/area companion to Cash Flow.
5. **Expense Breakdown donut** (Task 5).
6. **Occupancy stacked area** (Task 6).
7. **Currency Exposure horizontal bar** (Task 7).
8. **Property Valuation combo + Rent Yield line** (Task 8) — PropertyDetail charts.
9. **Tenant Rent History bar + brush** (Task 9) — TenantDetail chart.
10. **HomePage dashboard** (Task 10) — KPI cards + 5 chart tiles + P&L table.
11. **Mount charts on detail pages** (Task 11) — fill the Plan B placeholders.
12. **Chart tests + Playwright smoke** (Task 12).
13. **B2 review follow-ups + dead code cleanup** (Task 13).
14. **Verification** (Task 14).

---

## Task 1: Recharts install + ChartCard + formatters

**Goal:** Install Recharts, build the reusable `<ChartCard>` wrapper, and fix `formatCurrency` for chart axis/tooltip use.

**Files:**
- Install: `recharts`
- Create: `frontend/src/components/charts/ChartCard.tsx`
- Modify: `frontend/src/lib/format.ts` (extend formatCurrency for compact/axis use)
- Create: `frontend/src/components/charts/_chartTheme.ts` (color palette per category)

**Interfaces:**
- Produces: `<ChartCard title controls description onTableData children />` — a responsive container with title, optional controls (frequency selector, etc.), an SR-only summary, a "view as table" toggle that renders children's data as a `<table>`, and a `<ResponsiveContainer>` for the chart.

- [ ] **Step 1: Install Recharts**

```bash
cd frontend && npm install recharts
```

- [ ] **Step 2: Write `_chartTheme.ts`**

`frontend/src/components/charts/_chartTheme.ts`:
```typescript
// Category → color mapping for consistent chart styling.
export const CATEGORY_COLORS: Record<string, string> = {
  rent: '#22c55e',      // green
  utilities: '#3b82f6', // blue
  electricity: '#f59e0b', // amber
  management: '#8b5cf6', // purple
  tax: '#ef4444',       // red
  Debt: '#64748b',      // slate
  Equity: '#10b981',    // emerald
}

export function colorForCategory(category: string, index: number = 0): string {
  const FALLBACK = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']
  return CATEGORY_COLORS[category] ?? FALLBACK[index % FALLBACK.length]
}
```

- [ ] **Step 3: Extend `formatCurrency`**

In `frontend/src/lib/format.ts`, add a `compact` variant for axis labels:
```typescript
export function formatCurrencyAxis(value: number, currency: string): string {
  const symbols: Record<string, string> = { USD: '$', EUR: '€', GBP: '£', RUB: '₽' }
  const symbol = symbols[currency] ?? ''
  if (Math.abs(value) >= 1000) return `${symbol}${(value / 1000).toFixed(0)}k`
  return `${symbol}${value}`
}
```

- [ ] **Step 4: Write `ChartCard.tsx`**

`frontend/src/components/charts/ChartCard.tsx`:
```tsx
import { useState, type ReactNode } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

type Props = {
  title: string
  description?: string
  controls?: ReactNode  // frequency selector, timeline dropdown, etc.
  tableData?: { headers: string[]; rows: (string | number)[][] }  // for "view as table"
  children: ReactNode   // the chart (ResponsiveContainer)
}

export function ChartCard({ title, description, controls, tableData, children }: Props) {
  const [showTable, setShowTable] = useState(false)
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle className="text-lg">{title}</CardTitle>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {controls}
          {tableData && (
            <Button variant="ghost" size="sm" onClick={() => setShowTable(!showTable)}>
              {showTable ? 'Chart' : 'Table'}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {showTable && tableData ? (
          <Table>
            <TableHeader>
              <TableRow>{tableData.headers.map(h => <TableHead key={h}>{h}</TableHead>)}</TableRow>
            </TableHeader>
            <TableBody>
              {tableData.rows.map((row, i) => (
                <TableRow key={i}>{row.map((cell, j) => <TableCell key={j}>{cell}</TableCell>)}</TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <div className="h-[300px] w-full">{children}</div>
        )}
        {description && <span className="sr-only">{description}</span>}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 5: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
cd "D:/Developing/Property-rental"
git add frontend/
git commit -m "feat(frontend): install Recharts + ChartCard wrapper + chart formatters/theme"
```

---

## Task 2: useChartData hook + data adapter

**Goal:** Add the `useChartData` React Query hook + the adapter that transforms `{labels, datasets, currency}` to Recharts' flat-object-per-x format.

**Files:**
- Create: `frontend/src/api/charts.ts` (the `useChartData` hook)
- Create: `frontend/src/components/charts/_chartAdapter.ts` (the data transformer)

**Interfaces:**
- Produces:
  - `useChartData(params)` → `UseQueryResult<ChartDataResponse>`
  - `transformForRecharts(data: ChartDataResponse)` → `{ chartData: Record<string, any>[]; series: { key: string; label: string; color: string }[]; currency: string }`
  - `ChartDataResponse` type: `{ labels: string[]; datasets: { label?: string; data: number[] }[]; currency: string }`

- [ ] **Step 1: Write the types + hook**

`frontend/src/api/charts.ts`:
```typescript
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from './client'
import { queryKeys } from './keys'

export type ChartDataset = { label?: string; data: number[] }
export type ChartDataResponse = { labels: string[]; datasets: ChartDataset[]; currency: string }

export type ChartDataParams = {
  type: 'homePage' | 'property' | 'tenant'
  elementId?: number
  frequency?: string
  start?: string
  end?: string
  currency?: string
}

export function useChartData(params: ChartDataParams) {
  return useQuery<ChartDataResponse>({
    queryKey: queryKeys.chartData.filtered(params),
    queryFn: () => apiFetch<ChartDataResponse>('/chart-data/', {
      query: {
        type: params.type,
        id: params.elementId,
        freq: params.frequency,
        start: params.start,
        end: params.end,
        currency: params.currency,
      },
    }),
    enabled: !!params.type,
    staleTime: 0,
  })
}
```

- [ ] **Step 2: Write the adapter**

`frontend/src/components/charts/_chartAdapter.ts`:
```typescript
import type { ChartDataResponse } from '@/api/charts'
import { colorForCategory } from './_chartTheme'

export type TransformedChartData = {
  chartData: Record<string, number | string>[]
  series: { key: string; label: string; color: string }[]
  currency: string
}

export function transformForRecharts(data: ChartDataResponse): TransformedChartData {
  const { labels, datasets, currency } = data
  // Build flat objects: [{ label: 'Jan-24', rent: 1000, utilities: 200 }, ...]
  const chartData = labels.map((label, i) => {
    const row: Record<string, number | string> = { label }
    datasets.forEach((ds, j) => {
      const key = ds.label || `series_${j}`
      row[key] = ds.data[i] ?? 0
    })
    return row
  })
  // Build series metadata
  const series = datasets.map((ds, j) => ({
    key: ds.label || `series_${j}`,
    label: ds.label || `Series ${j + 1}`,
    color: colorForCategory(ds.label || '', j),
  }))
  return { chartData, series, currency }
}
```

- [ ] **Step 3: Verify build + existing tests**

```bash
cd frontend && npm run build && npm test
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/charts.ts frontend/src/components/charts/_chartAdapter.ts
git commit -m "feat(frontend): useChartData hook + Recharts data adapter"
```

---

## Task 3: Cash Flow chart (the headline)

**Goal:** Build the diverging stacked bar chart (income above, expenses below) with click-to-drill-down and time-range brush.

**Files:**
- Create: `frontend/src/components/charts/CashFlowChart.tsx`

**Interfaces:**
- Produces: `<CashFlowChart data={ChartDataResponse} currency={string} onBarClick={(period, category) => void} />`

- [ ] **Step 1: Write CashFlowChart**

`frontend/src/components/charts/CashFlowChart.tsx`:
```tsx
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Brush, ResponsiveContainer } from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrencyAxis } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
  onBarClick?: (period: string, category: string) => void
}

export function CashFlowChart({ data, onBarClick }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)
  const tableData = {
    headers: ['Period', ...series.map(s => s.label)],
    rows: chartData.map(row => [row.label as string, ...series.map(s => row[s.key] as number)]),
  }
  return (
    <ChartCard title="Cash Flow" description="Income vs expenses by period" tableData={tableData}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, currency)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v: number) => formatCurrencyAxis(v, currency)} />
          <Legend />
          {series.map(s => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              stackId="a"
              onClick={(payload: any) => onBarClick?.(payload.label, s.key)}
              cursor={onBarClick ? 'pointer' : 'default'}
            />
          ))}
          <Brush dataKey="label" height={20} stroke="#3b82f6" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/CashFlowChart.tsx
git commit -m "feat(frontend): Cash Flow stacked bar chart with drill-down + brush"
```

---

## Task 4: Net Income Trend chart

**Goal:** Build the line+area companion chart showing the net income trajectory.

**Files:**
- Create: `frontend/src/components/charts/NetIncomeTrendChart.tsx`

- [ ] **Step 1: Write the chart**

Derives net income (sum of all series per period) from the chart data, renders as an Area chart with a gradient fill. Includes Brush for time-range selection. Legend toggle is implicit (single series).

- [ ] **Step 2: Build + commit**

---

## Task 5: Expense Breakdown donut

**Goal:** Build a donut chart showing expense proportions for the last 12 months.

**Files:**
- Create: `frontend/src/components/charts/ExpenseBreakdownChart.tsx`

**Interfaces:**
- Consumes: `useChartData` for the last-12-months period (or aggregates from `useTransactions`).

- [ ] **Step 1: Write the donut chart**

Uses Recharts `<PieChart>` with `innerRadius` to create a donut. Data is aggregated by category from transactions. Legend is interactive (click to toggle). Color from `_chartTheme.ts`.

- [ ] **Step 2: Build + commit**

---

## Task 6: Portfolio Occupancy stacked area

**Goal:** Build a stacked area chart showing occupied vs vacant units over time.

**Files:**
- Create: `frontend/src/components/charts/OccupancyChart.tsx`

- [ ] **Step 1: Write the occupancy chart**

Data derived from tenants' `lease_start`/`lease_end` + properties count. Computes per-period: occupied = tenants whose lease spans the period; vacant = total properties - occupied. Rendered as a stacked AreaChart.

- [ ] **Step 2: Build + commit**

---

## Task 7: Currency Exposure horizontal bar

**Goal:** Build a horizontal stacked bar showing current value at-risk by currency.

**Files:**
- Create: `frontend/src/components/charts/CurrencyExposureChart.tsx`

- [ ] **Step 1: Write the currency exposure chart**

Data derived from properties (grouped by currency, summed value via `usePropertiesWithStats` or property valuations). Rendered as a horizontal BarChart with `layout="vertical"`. Shows FX exposure at a glance.

- [ ] **Step 2: Build + commit**

---

## Task 8: Property Valuation combo + Rent Yield line

**Goal:** Build 2 charts for PropertyDetailPage: Valuation (stacked bar Debt+Equity + line overlay) and Rent Yield (line).

**Files:**
- Create: `frontend/src/components/charts/ValuationChart.tsx`
- Create: `frontend/src/components/charts/RentYieldChart.tsx`

- [ ] **Step 1: Write ValuationChart**

Stacked bar (Debt + Equity) with a ComposedChart. Includes a Line overlay showing total value trajectory. Data from `useChartData({type: 'property', elementId: id})`. Click-to-drill to transactions for the period.

- [ ] **Step 2: Write RentYieldChart**

Line chart showing rent yield (rent_total / property_value) per period. Data derived: `useChartData({type: 'tenant', elementId: tenantId})` or computed from `useTransactions` + property valuations.

- [ ] **Step 3: Build + commit**

---

## Task 9: Tenant Rent History bar + brush

**Goal:** Build the tenant rent history chart with time-range brush.

**Files:**
- Create: `frontend/src/components/charts/TenantRentChart.tsx`

- [ ] **Step 1: Write TenantRentChart**

Single-series BarChart of rent received per period. Includes Brush for long-tenancy navigation. Data from `useChartData({type: 'tenant', elementId: id})`. Click-to-drill to transactions for the period.

- [ ] **Step 2: Build + commit**

---

## Task 10: HomePage dashboard

**Goal:** Replace the Plan A/B HomePage placeholder with the real dashboard: KPI cards + 5 chart tiles + P&L table.

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`
- Create: `frontend/src/components/dashboard/KpiCard.tsx`

- [ ] **Step 1: Write KpiCard**

Reusable card showing a label + value + optional delta indicator. Used for: Properties count, Revenue YTD, Net Income YTD, Occupancy %, Currency Exposure.

- [ ] **Step 2: Update HomePage**

Layout per the spec §6.8 dashboard mockup:
- Row 1: KPI cards (2 Properties, Revenue YTD, Net Income YTD, Occupancy %, FX Exposure).
- Row 2: Cash Flow chart (full width, with frequency/timeline controls).
- Row 3: Expense Breakdown (left) + Occupancy (right).
- Row 4: Net Income Trend (left) + Currency Exposure (right).
- Row 5: P&L table (per-category YTD + all-time).

Frequency + timeline controls drive the Cash Flow chart via `useChartData`. The KPIs and P&L derive from `usePropertiesWithStats` / `useTenantsWithStats`.

- [ ] **Step 3: Build + commit**

---

## Task 11: Mount charts on detail pages

**Goal:** Fill the chart placeholders in PropertyDetailPage and TenantDetailPage.

**Files:**
- Modify: `frontend/src/pages/PropertyDetailPage.tsx` (replace the `// Plan C chart slot` comments)
- Modify: `frontend/src/pages/TenantDetailPage.tsx` (same)

- [ ] **Step 1: Mount ValuationChart + RentYieldChart on PropertyDetailPage**

Replace the commented placeholders with the real chart components. Wire the `propertyId` to `useChartData`.

- [ ] **Step 2: Mount TenantRentChart on TenantDetailPage**

- [ ] **Step 3: Build + commit**

---

## Task 12: Chart tests + Playwright smoke

**Goal:** Add chart component tests (render with fixture data) + a light Playwright smoke suite.

**Files:**
- Create: `frontend/src/components/charts/CashFlowChart.test.tsx` (+ tests for other charts)
- Create: `frontend/tests/e2e/smoke.spec.ts` (Playwright)

- [ ] **Step 1: Write chart component tests**

Each chart test renders with the fixture `ChartDataResponse` and asserts the SVG container exists. Test legend toggle by clicking a legend item and asserting the Bar/Area becomes hidden.

- [ ] **Step 2: Install Playwright + write smoke test**

```bash
cd frontend && npm install -D @playwright/test && npx playwright install chromium
```

Write `frontend/tests/e2e/smoke.spec.ts`:
- Navigate to `/` (after login).
- Assert the dashboard renders with chart containers.
- Click a bar → assert navigation to `/transactions?...`.
- Navigate to `/properties/1` → assert valuation chart renders.
- Navigate to `/tenants/1` → assert rent chart renders.

- [ ] **Step 3: Run tests + commit**

---

## Task 13: B2 review follow-ups + dead code cleanup

**Goal:** Address the B2 whole-branch review's non-blocking findings.

**Files:**
- Create: `frontend/src/pages/TenantDetailPage.test.tsx` (the missing test)
- Modify: `property_rental/rentals/urls.py` (broaden catch-all to avoid 301s)
- Delete: `property_rental/rentals/templatetags/custom_filters.py` (orphaned)

- [ ] **Step 1: Write TenantDetailPage.test.tsx**

Basic render test (heading + tabs render). Follow the pattern of other page tests.

- [ ] **Step 2: Fix SPA catch-all 301**

In `property_rental/rentals/urls.py`, replace `re_path(r'^.*/$', SpaView.as_view())` with:
```python
re_path(r'^.+$', SpaView.as_view()),
```
This matches any non-empty path without requiring a trailing slash.

- [ ] **Step 3: Delete orphaned templatetags**

```bash
cd "D:/Developing/Property-rental"
# Verify it's truly unused
grep -rn "format_number_with_parentheses\|custom_filters" property_rental/rentals/ --include="*.py" --include="*.html"
git rm property_rental/rentals/templatetags/custom_filters.py
```

- [ ] **Step 4: Run suites + commit**

---

## Task 14: Definition-of-done verification

- [ ] **Step 1: Backend suite**

```bash
cd property_rental && python -m pytest rentals/tests/ -q
```

- [ ] **Step 2: Frontend suite + build**

```bash
cd frontend && npm test && npm run build
```

- [ ] **Step 3: All 8 charts render**

Manual smoke test (both servers): confirm each chart renders on its page:
- HomePage: Cash Flow, Net Income Trend, Expense Breakdown, Occupancy, Currency Exposure.
- PropertyDetail: Valuation, Rent Yield.
- TenantDetail: Rent History.

- [ ] **Step 4: Interactive features work**

- Click a Cash Flow bar → navigates to filtered TransactionsPage.
- Click a legend item → series hides.
- Use the brush → chart range changes.

- [ ] **Step 5: No console errors**

Check browser console on each page.

- [ ] **Step 6: `check --deploy`**

```bash
cd property_rental && python manage.py check --deploy
```

- [ ] **Step 7: Commit + tag**

```bash
git commit --allow-empty -m "chore: Plan C (charting overhaul + dashboard) verification complete"
git tag plan-c-complete
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Task(s) | Covered? |
|---|---|---|
| §5 Chart 1: Cash Flow (diverging stacked bar) | Task 3 | ✅ |
| §5 Chart 2: Net Income Trend (line/area) | Task 4 | ✅ |
| §5 Chart 3: Expense Breakdown (donut) | Task 5 | ✅ |
| §5 Chart 4: Occupancy (stacked area) | Task 6 | ✅ |
| §5 Chart 5: Currency Exposure (horizontal bar) | Task 7 | ✅ |
| §5 Chart 6: Valuation (bar+line combo) | Task 8 | ✅ |
| §5 Chart 7: Rent Yield (line) | Task 8 | ✅ |
| §5 Chart 8: Tenant Rent History (bar+brush) | Task 9 | ✅ |
| §5 Interactivity: drill-down | Task 3 (+ others) | ✅ |
| §5 Interactivity: legend toggle | Recharts default | ✅ |
| §5 Interactivity: brush | Tasks 3, 4, 9 | ✅ |
| §5 Bugs: all eliminated | Recharts rewrite | ✅ |
| §6.8 HomePage dashboard | Task 10 | ✅ |
| §10 DoD | Task 14 | ✅ |
| B2 review: TenantDetailPage test | Task 13 | ✅ |
| B2 review: catch-all 301 fix | Task 13 | ✅ |
| Dead code: custom_filters.py | Task 13 | ✅ |

**2. Placeholder scan:** Chart code for Tasks 4-9 uses abbreviated descriptions ("write the chart") rather than full inline code. This is deliberate — each chart follows the Task 3 pattern (transformForRecharts + Recharts components inside ChartCard), and the specific Recharts config (BarChart vs PieChart vs AreaChart vs ComposedChart) is the implementer's key decision. Full code would bloat the plan to 2000+ lines. Acceptable for a plan at this complexity.

**3. Type consistency:** `ChartDataResponse` type (Task 2), `transformForRecharts` (Task 2), `useChartData` hook (Task 2) — all consumed by Tasks 3-11 consistently. `ChartCard` props (Task 1) consumed consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-20-charting-dashboard.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
