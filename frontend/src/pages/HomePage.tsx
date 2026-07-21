// frontend/src/pages/HomePage.tsx
//
// Real dashboard (Plan C Task 10). Replaces the minimal "two counts"
// placeholder from Plan B2 with:
//
//   1. KPI row (5 cards): property count, revenue YTD, net income YTD,
//      occupancy %, FX exposure.
//   2. Charts:
//        - Cash Flow (full-width, with frequency + timeline selectors that
//          re-fire the chart-data request).
//        - Expense breakdown + Occupancy (side-by-side).
//        - Net income trend + Currency exposure (side-by-side).
//   3. P&L table — derived from the same with_stats aggregations the KPIs
//      use, one row per property, sortable by net income YTD.
//
// Charts are powered by `useChartData({ type: 'homePage', frequency, start,
// end })`; KPIs derive from `usePropertiesWithStats` and
// `useTenantsWithStats` (the same hooks every other page uses, so React
// Query dedupes the round-trips).
//
// Drill-down: clicking a Cash Flow bar segment navigates to
// /transactions?from=...&to=...&category=... for the period + category.
// `periodLabelToRange` translates the chart's period label (`Jan-24`,
// `Q1 24`, `2024`) into a `YYYY-MM-DD` range that the TransactionsPage
// filter already understands (it reads `from`/`to`/`category` from the URL
// query string).
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useChartData } from '@/api/charts'
import { usePropertiesWithStats } from '@/api/properties'
import { useTenantsWithStats } from '@/api/tenants'
import { CashFlowChart } from '@/components/charts/CashFlowChart'
import { ExpenseBreakdownChart } from '@/components/charts/ExpenseBreakdownChart'
import { NetIncomeTrendChart } from '@/components/charts/NetIncomeTrendChart'
import { OccupancyChart } from '@/components/charts/OccupancyChart'
import { CurrencyExposureChart } from '@/components/charts/CurrencyExposureChart'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { ErrorState } from '@/components/states/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatDate } from '@/lib/format'

// Frequency + timeline options that mirror the backend `chart_data` view's
// `freq` and the `calculate_from_date` timelines. Keys must match the
// backend strings (M / Q / Y for frequency; YTD / 3m / 6m / 12m / 3Y / 5Y
// for timeline).
const FREQUENCY_OPTIONS = [
  { value: 'M', label: 'Monthly' },
  { value: 'Q', label: 'Quarterly' },
  { value: 'Y', label: 'Yearly' },
] as const

const TIMELINE_OPTIONS = [
  { value: 'YTD', label: 'Year to date' },
  { value: '3m', label: 'Last 3 months' },
  { value: '6m', label: 'Last 6 months' },
  { value: '12m', label: 'Last 12 months' },
  { value: '3Y', label: 'Last 3 years' },
  { value: '5Y', label: 'Last 5 years' },
] as const

type Frequency = (typeof FREQUENCY_OPTIONS)[number]['value']
type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

// Compute the `YYYY-MM-DD` `from`/`to` window for a timeline ending today.
// Mirrors the backend `calculate_from_date` (see `rentals/utils.py`) so the
// chart-data request the dashboard fires lines up with what the user
// thinks they're asking for.
function timelineToRange(timeline: Timeline): { from: string; to: string } {
  const today = new Date()
  const to = today.toISOString().slice(0, 10)
  const from = new Date(today)
  switch (timeline) {
    case 'YTD':
      from.setMonth(0, 1) // Jan 1 of current year
      break
    case '3m':
      from.setMonth(from.getMonth() - 3)
      break
    case '6m':
      from.setMonth(from.getMonth() - 6)
      break
    case '12m':
      from.setFullYear(from.getFullYear() - 1)
      break
    case '3Y':
      from.setFullYear(from.getFullYear() - 3)
      break
    case '5Y':
      from.setFullYear(from.getFullYear() - 5)
      break
  }
  return { from: from.toISOString().slice(0, 10), to }
}

// Convert a chart period label back into a date range for drill-down. The
// backend's `chart_labels` emits `Jan-24` (M), `Q1 24` (Q), `2024` (Y); we
// parse each back into a `YYYY-MM-DD` window covering that period.
function periodLabelToRange(
  label: string,
  frequency: Frequency,
): { from: string; to: string } | null {
  if (frequency === 'Y') {
    const year = Number(label)
    if (!Number.isFinite(year)) return null
    return {
      from: `${year}-01-01`,
      to: `${year}-12-31`,
    }
  }
  if (frequency === 'Q') {
    // e.g. "Q1 24" -> 2024-01-01..2024-03-31
    const m = label.match(/Q([1-4])\s+(\d{2,4})/)
    if (!m) return null
    const q = Number(m[1])
    let year = Number(m[2])
    if (year < 100) year += 2000
    const startMonth = (q - 1) * 3 + 1
    const endMonth = startMonth + 2
    const lastDay = new Date(year, endMonth, 0).getDate()
    return {
      from: `${year}-${String(startMonth).padStart(2, '0')}-01`,
      to: `${year}-${String(endMonth).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
    }
  }
  // Monthly: "Jan-24" -> 2024-01-01..2024-01-31
  const m = label.match(/^([A-Za-z]{3})-(\d{2,4})$/)
  if (!m) return null
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const monthIdx = monthNames.indexOf(m[1])
  if (monthIdx < 0) return null
  let year = Number(m[2])
  if (year < 100) year += 2000
  const lastDay = new Date(year, monthIdx + 1, 0).getDate()
  return {
    from: `${year}-${String(monthIdx + 1).padStart(2, '0')}-01`,
    to: `${year}-${String(monthIdx + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
  }
}

export function HomePage() {
  const navigate = useNavigate()

  // Frequency + timeline drive the Cash Flow + Net Income Trend chart-data
  // requests. Default to monthly + last 12 months so the dashboard has
  // visible history on first load.
  const [frequency, setFrequency] = useState<Frequency>('M')
  const [timeline, setTimeline] = useState<Timeline>('12m')

  const range = useMemo(() => timelineToRange(timeline), [timeline])

  // ---- Data hooks ----------------------------------------------------------
  // KPIs derive from the with_stats aggregations every other page already
  // caches. We aggregate client-side across properties so a missing
  // `currency` conversion on the dashboard doesn't crash the page (mixed
  // currencies sum naively here — same caveat as CurrencyExposureChart).
  const propertiesStats = usePropertiesWithStats()
  const tenantsStats = useTenantsWithStats()

  // One chart-data request for the headline bar chart; the same response
  // powers both Cash Flow and (via Net Income Trend's client-side sum) the
  // net income trajectory, so a single round-trip feeds two tiles.
  const chartQuery = useChartData({
    type: 'homePage',
    frequency,
    start: range.from,
    end: range.to,
  })
  // Expense breakdown consumes a 12-month window regardless of the Cash
  // Flow timeline selector — that way the donut reflects recent spend
  // patterns even when the user scrubs the Cash Flow chart to "YTD".
  const expenseRange = useMemo(() => timelineToRange('12m'), [])
  const expenseQuery = useChartData({
    type: 'homePage',
    frequency: 'M',
    start: expenseRange.from,
    end: expenseRange.to,
  })

  // ---- KPI derivations -----------------------------------------------------
  const kpis = useMemo(() => {
    const props = propertiesStats.data ?? []
    const tenants = tenantsStats.data ?? []
    const totalUnits = props.length
    const revenueYTD = props.reduce((acc, p) => acc + (p.gross_income_ytd ?? 0), 0)
    const netIncomeYTD = props.reduce((acc, p) => acc + (p.net_income_ytd ?? 0), 0)

    // Occupancy: tenants with an active lease (`lease_end` is null or in
    // the future) divided by total units. Same status logic the
    // OccupancyChart uses; we duplicate it because the chart already
    // exposes the most-recent point as its last bucket and we want the KPI
    // value to be authoritative regardless of chart bucketing.
    const today = new Date().toISOString().slice(0, 10)
    const occupied = tenants.filter((t) => {
      if (!t.lease_start || t.lease_start > today) return false
      if (t.lease_end && t.lease_end < today) return false
      return true
    }).length
    const occupancyPct = totalUnits > 0 ? Math.round((occupied / totalUnits) * 100) : 0

    // FX exposure: number of distinct currencies in the portfolio + their
    // aggregate lifetime net income (a rough proxy for value at risk). We
    // surface "N currencies" as the headline and let the chart tile show
    // the per-currency split.
    const currencies = new Set(props.map((p) => p.currency || '???'))

    return {
      totalUnits,
      revenueYTD,
      netIncomeYTD,
      occupancyPct,
      currencyCount: currencies.size,
    }
  }, [propertiesStats.data, tenantsStats.data])

  // Aggregate display currency for KPI values: pick the most common
  // currency across properties (or USD if none). Purely cosmetic — same
  // mixed-currency caveat as CurrencyExposureChart applies.
  const kpiCurrency = useMemo(() => {
    const counts = new Map<string, number>()
    for (const p of propertiesStats.data ?? []) {
      counts.set(p.currency || '???', (counts.get(p.currency || '???') ?? 0) + 1)
    }
    let best = 'USD'
    let bestCount = 0
    for (const [cur, count] of counts) {
      if (count > bestCount) {
        best = cur
        bestCount = count
      }
    }
    return best
  }, [propertiesStats.data])

  // ---- P&L table rows ------------------------------------------------------
  // Sorted by net income YTD desc so the biggest contributors sit at the
  // top. We deliberately don't reuse `DataTable` here — the dashboard P&L
  // is read-only, doesn't need the row-click affordance, and the shadcn
  // `<Table>` primitives read cleaner for a 4-column summary.
  const pnlRows = useMemo(() => {
    const rows = (propertiesStats.data ?? []).map((p) => ({
      id: p.id,
      name: p.name,
      currency: p.currency,
      revenueYTD: p.gross_income_ytd ?? 0,
      expensesYTD: p.expenses_ytd ?? 0,
      netIncomeYTD: p.net_income_ytd ?? 0,
    }))
    rows.sort((a, b) => b.netIncomeYTD - a.netIncomeYTD)
    return rows
  }, [propertiesStats.data])

  // ---- Cash Flow drill-down ------------------------------------------------
  const onBarClick = (period: string, category: string) => {
    const r = periodLabelToRange(period, frequency)
    if (!r) return
    const params = new URLSearchParams({
      from: r.from,
      to: r.to,
      category,
    })
    navigate(`/transactions?${params.toString()}`)
  }

  // ---- Render guards -------------------------------------------------------
  // Charts self-skeleton on their own (each chart's ChartCard shows
  // "Loading…" when its data is empty); we only need to guard the KPIs +
  // P&L table here.
  const isLoading = propertiesStats.isLoading || tenantsStats.isLoading
  const isError = propertiesStats.isError || tenantsStats.isError

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* ---- KPI row ---------------------------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard
          label="Properties"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-10" />
            ) : (
              kpis.totalUnits
            )
          }
        />
        <KpiCard
          label="Revenue (YTD)"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              formatCurrency(kpis.revenueYTD, kpiCurrency, { compact: true })
            )
          }
        />
        <KpiCard
          label="Net income (YTD)"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              formatCurrency(kpis.netIncomeYTD, kpiCurrency, { compact: true })
            )
          }
        />
        <KpiCard
          label="Occupancy"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-12" />
            ) : (
              `${kpis.occupancyPct}%`
            )
          }
        />
        <KpiCard
          label="FX exposure"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-16" />
            ) : (
              `${kpis.currencyCount} ${kpis.currencyCount === 1 ? 'currency' : 'currencies'}`
            )
          }
        />
      </div>

      {/* ---- Cash Flow (full-width) ------------------------------------- */}
      {/* The chart itself owns its loading state via ChartCard; we just
          pass the data through and let the controls live in the card
          header so they're co-located with the chart they affect. */}
      <CashFlowChart
        data={chartQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        onBarClick={onBarClick}
        controls={
          <>
            <Select
              value={frequency}
              onValueChange={(v) => setFrequency(v as Frequency)}
            >
              <SelectTrigger className="h-8 w-[110px]" aria-label="Frequency">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FREQUENCY_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={timeline}
              onValueChange={(v) => setTimeline(v as Timeline)}
            >
              <SelectTrigger className="h-8 w-[150px]" aria-label="Timeline">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIMELINE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        }
      />

      {/* ---- Expense breakdown + Occupancy (side-by-side) --------------- */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ExpenseBreakdownChart
          data={expenseQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        />
        <OccupancyChart />
      </div>

      {/* ---- Net income trend + Currency exposure (side-by-side) -------- */}
      <div className="grid gap-4 lg:grid-cols-2">
        <NetIncomeTrendChart
          data={chartQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        />
        <CurrencyExposureChart />
      </div>

      {/* ---- P&L table -------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle>Profit &amp; Loss (YTD)</CardTitle>
        </CardHeader>
        <CardContent>
          {isError ? (
            <ErrorState
              message="Failed to load property stats"
              onRetry={() => {
                propertiesStats.refetch()
                tenantsStats.refetch()
              }}
            />
          ) : isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : pnlRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No properties yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Property</TableHead>
                  <TableHead>Currency</TableHead>
                  <TableHead className="text-right">Revenue YTD</TableHead>
                  <TableHead className="text-right">Expenses YTD</TableHead>
                  <TableHead className="text-right">Net YTD</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pnlRows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.name}</TableCell>
                    <TableCell>{row.currency}</TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(row.revenueYTD, row.currency, { compact: true })}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(row.expensesYTD, row.currency, { compact: true })}
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatCurrency(row.netIncomeYTD, row.currency, { compact: true })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Hidden export for tests / a11y tools that want the timeline label
          as plain text — keeps the dashboard's "as of" date reachable
          without polluting the visible layout. */}
      <span className="sr-only">
        Dashboard timeline {timeline} ({formatDate(range.from)} to {formatDate(range.to)})
      </span>
    </div>
  )
}
