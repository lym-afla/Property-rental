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
//   3. P&L table — per-category breakdown (income + expense sections) with
//      All-time + YTD columns, derived from `useChartData({type: 'homePage',
//      frequency: 'Y'})`. The chart-data response returns one dataset per
//      category; summing each dataset gives the all-time / YTD total per
//      category. (Previously this table only showed 3 aggregated rows from
//      `with_stats`, which lost the per-category detail the old Django
//      template exposed.)
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
import { formatAccounting, formatCurrency, formatDate } from '@/lib/format'

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
  { value: 'All', label: 'All time' },
] as const

// Occupancy history is derived client-side from tenants (no chart-data
// round-trip), so its period selector uses a simpler month-count model
// than the chart-data timelines.
const OCCUPANCY_PERIOD_OPTIONS = [
  { value: '12m', label: 'Last 12 months' },
  { value: '24m', label: 'Last 24 months' },
  { value: 'all', label: 'All history' },
] as const

type Frequency = (typeof FREQUENCY_OPTIONS)[number]['value']
type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']
type OccupancyPeriod = (typeof OCCUPANCY_PERIOD_OPTIONS)[number]['value']

// Compute the `YYYY-MM-DD` `from`/`to` window for a timeline ending today.
// Mirrors the backend `calculate_from_date` (see `rentals/utils.py`) so the
// chart-data request the dashboard fires lines up with what the user
// thinks they're asking for.
function timelineToRange(timeline: Timeline): { from: string; to: string } {
  const today = new Date()
  const to = today.toISOString().slice(0, 10)
  // `All` uses the backend's all-time sentinel `1900-01-01` — the
  // chart-data service rewrites it to the property set's earliest
  // transaction date (see `services/charts.py::get_chart_data`).
  if (timeline === 'All') return { from: '1900-01-01', to }
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

// Convert an occupancy period selection into a month count. `all` returns
// undefined so the chart knows to span the full tenant history.
function occupancyPeriodToMonths(period: OccupancyPeriod): number | undefined {
  if (period === 'all') return undefined
  return period === '12m' ? 12 : 24
}

export function HomePage() {
  const navigate = useNavigate()

  // Frequency + timeline drive the Cash Flow + Net Income Trend chart-data
  // requests. Default to monthly + last 12 months so the dashboard has
  // visible history on first load.
  const [frequency, setFrequency] = useState<Frequency>('M')
  const [timeline, setTimeline] = useState<Timeline>('12m')

  // Each secondary chart owns its own timeline selector so users can scope
  // the expense donut and the net income trend independently of the Cash
  // Flow headline chart. Net Income Trend defaults to the same window as
  // Cash Flow; Expense Breakdown defaults to 12m (recent spend patterns).
  const [expenseTimeline, setExpenseTimeline] = useState<Timeline>('12m')
  const [netIncomeTimeline, setNetIncomeTimeline] = useState<Timeline>('12m')

  // Occupancy history length: number of months to look back, or 'all' for
  // the full tenant history. Default 12m keeps the chart readable.
  const [occupancyPeriod, setOccupancyPeriod] =
    useState<OccupancyPeriod>('12m')

  const range = useMemo(() => timelineToRange(timeline), [timeline])
  const expenseRange = useMemo(
    () => timelineToRange(expenseTimeline),
    [expenseTimeline],
  )
  const netIncomeRange = useMemo(
    () => timelineToRange(netIncomeTimeline),
    [netIncomeTimeline],
  )

  // ---- Data hooks ----------------------------------------------------------
  // KPIs derive from the with_stats aggregations. The dashboard sums every
  // property into a single portfolio number, so we request stats FX-
  // converted into USD (the user's `default_currency`) — summing native
  // RUB + GBP figures into one total would mix units. The Properties PAGE
  // stays native-currency per row; this dashboard hook is USD-scoped.
  const propertiesStats = usePropertiesWithStats(undefined, 'USD')
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
  // Expense breakdown consumes its own chart-data request driven by the
  // expense timeline selector — the donut reflects the spend window the
  // user picked rather than always defaulting to 12 months.
  const expenseQuery = useChartData({
    type: 'homePage',
    frequency: 'M',
    start: expenseRange.from,
    end: expenseRange.to,
  })
  // Net Income Trend gets its own request so its timeline selector is
  // independent of the Cash Flow headline chart.
  const netIncomeQuery = useChartData({
    type: 'homePage',
    frequency,
    start: netIncomeRange.from,
    end: netIncomeRange.to,
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

  // Aggregate display currency for KPI values: stats are FX-converted to a
  // single target currency on the backend (exposed as `stats_currency`,
  // almost always `USD`). The previous code picked the most common NATIVE
  // `currency` across properties — which was wrong, because the stats
  // values themselves are denominated in `stats_currency`, not the native
  // currency. We now use `stats_currency` so the symbol matches the number.
  const kpiCurrency = useMemo(() => {
    const first = (propertiesStats.data ?? [])[0]
    return first?.stats_currency ?? 'USD'
  }, [propertiesStats.data])

  // ---- P&L per-category breakdown -----------------------------------------
  // The user wants the OLD-style P&L with every category line, not just
  // Gross/Expenses/Net. `with_stats` only returns aggregate totals, so we
  // fire a `chart-data` request (yearly frequency over a wide range) and
  // sum each dataset to get per-category all-time / YTD totals. The
  // chart-data `homePage` branch emits one dataset per category with its
  // monthly/quarterly/yearly totals; summing the `data` array gives the
  // grand total for that category over the requested window.
  //
  // All-time window: from a far-back sentinel (`1900-01-01`) through today.
  // The backend's chart_data service treats `1900-01-01` as the "All time"
  // sentinel and rewrites it to the property set's earliest transaction
  // date (see `services/charts.py::get_chart_data`).
  // YTD window: Jan 1 of the current year through Dec 31 (the chart_data
  // service clamps the upper bound to today internally for `homePage`).
  const today = new Date()
  const todayIso = today.toISOString().slice(0, 10)
  const yearStart = `${today.getFullYear()}-01-01`
  const yearEnd = `${today.getFullYear()}-12-31`
  const pnlAllTimeQuery = useChartData({
    type: 'homePage',
    frequency: 'Y',
    start: '1900-01-01',
    end: todayIso,
  })
  const pnlYtdQuery = useChartData({
    type: 'homePage',
    frequency: 'Y',
    start: yearStart,
    end: yearEnd,
  })

  // Income vs expense classification — mirrors `rentals/constants.py`.
  const INCOME_CATEGORIES = ['rent', 'other_income']

  // Sum each dataset's `data` array to get the category total for the
  // requested window. The chart-data service returns negatives for
  // expenses (transactions store expense amounts as negative); we keep
  // the sign through to the table and format via `formatAccounting`,
  // which renders negatives as `$(-1,234)`.
  const pnlRows = useMemo(() => {
    const sum = (datasets: { label?: string; data: number[] }[], predicate: (label: string) => boolean) => {
      const rows: { label: string; total: number }[] = []
      for (const ds of datasets) {
        const label = ds.label ?? ''
        if (!predicate(label)) continue
        const total = (ds.data ?? []).reduce((acc, v) => acc + (Number(v) || 0), 0)
        rows.push({ label, total })
      }
      return rows
    }
    const isIncome = (label: string) => INCOME_CATEGORIES.includes(label)
    const allTimeDatasets = pnlAllTimeQuery.data?.datasets ?? []
    const ytdDatasets = pnlYtdQuery.data?.datasets ?? []
    const incomeAllTime = sum(allTimeDatasets, isIncome)
    // Expense categories come back negative from chart-data; keep the
    // sign so `formatAccounting` can render the brackets.
    const expenseAllTime = sum(allTimeDatasets, (l) => !isIncome(l) && l.length > 0)
    const incomeYtd = sum(ytdDatasets, isIncome)
    const expenseYtd = sum(ytdDatasets, (l) => !isIncome(l) && l.length > 0)
    const totalIncomeAll = incomeAllTime.reduce((acc, r) => acc + r.total, 0)
    const totalIncomeYtd = incomeYtd.reduce((acc, r) => acc + r.total, 0)
    const totalExpenseAll = expenseAllTime.reduce((acc, r) => acc + r.total, 0)
    const totalExpenseYtd = expenseYtd.reduce((acc, r) => acc + r.total, 0)
    return {
      incomeAllTime,
      incomeYtd,
      expenseAllTime,
      expenseYtd,
      totalIncomeAll,
      totalIncomeYtd,
      totalExpenseAll,
      totalExpenseYtd,
      netIncomeAll: totalIncomeAll + totalExpenseAll, // expenses are negative
      netIncomeYtd: totalIncomeYtd + totalExpenseYtd,
    }
  }, [pnlAllTimeQuery.data, pnlYtdQuery.data])

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
              formatCurrency(kpis.revenueYTD, kpiCurrency)
            )
          }
        />
        <KpiCard
          label="Net income (YTD)"
          value={
            isLoading ? (
              <Skeleton className="h-7 w-24" />
            ) : (
              formatCurrency(kpis.netIncomeYTD, kpiCurrency)
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
          controls={
            <Select
              value={expenseTimeline}
              onValueChange={(v) => setExpenseTimeline(v as Timeline)}
            >
              <SelectTrigger className="h-8 w-[150px]" aria-label="Expense timeline">
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
          }
        />
        <OccupancyChart
          monthsBack={occupancyPeriodToMonths(occupancyPeriod)}
          controls={
            <Select
              value={occupancyPeriod}
              onValueChange={(v) => setOccupancyPeriod(v as OccupancyPeriod)}
            >
              <SelectTrigger className="h-8 w-[150px]" aria-label="Occupancy period">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {OCCUPANCY_PERIOD_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          }
        />
      </div>

      {/* ---- Net income trend + Currency exposure (side-by-side) -------- */}
      <div className="grid gap-4 lg:grid-cols-2">
        <NetIncomeTrendChart
          data={netIncomeQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
          controls={
            <Select
              value={netIncomeTimeline}
              onValueChange={(v) => setNetIncomeTimeline(v as Timeline)}
            >
              <SelectTrigger className="h-8 w-[150px]" aria-label="Net income timeline">
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
          }
        />
        <CurrencyExposureChart />
      </div>

      {/* ---- P&L table -------------------------------------------------- */}
      {/* Per-category P&L breakdown with All-time + YTD columns. The chart-data
          request gives us one dataset per category; we sum each one to get
          the totals displayed here. Currency is the backend's `stats_currency`
          (USD by default) since chart-data FX-converts everything. Layout:
          income categories first, then "Total revenue", then expense
          categories (alphabetical, kept negative), then "Total expenses"
          and "Net income". `formatAccounting` renders negatives as
          `$(-1,234)` so the sign convention is unambiguous. */}
      <Card>
        <CardHeader>
          <CardTitle>Profit &amp; Loss</CardTitle>
          <p className="text-xs text-muted-foreground">
            All values in {kpiCurrency}. Per-category breakdown across all owned
            properties, FX-converted on the backend.
          </p>
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
          ) : (propertiesStats.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No properties yet.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">All time</TableHead>
                  <TableHead className="text-right">YTD</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Income section — one row per income category. */}
                {pnlRows.incomeAllTime.map((row, idx) => {
                  const ytdMatch = pnlRows.incomeYtd.find(
                    (r) => r.label === row.label,
                  )
                  return (
                    <TableRow key={`income-${row.label}-${idx}`}>
                      <TableCell className="font-medium capitalize">
                        {row.label}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatAccounting(row.total, kpiCurrency)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatAccounting(ytdMatch?.total ?? 0, kpiCurrency)}
                      </TableCell>
                    </TableRow>
                  )
                })}
                {/* Total revenue row. */}
                <TableRow className="border-t">
                  <TableCell className="font-bold">Total revenue</TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.totalIncomeAll, kpiCurrency)}
                  </TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.totalIncomeYtd, kpiCurrency)}
                  </TableCell>
                </TableRow>
                {/* Expense section — one row per expense category. Expenses
                    come back negative from chart-data, kept negative so
                    `formatAccounting` renders brackets. Sorted
                    alphabetically by label. */}
                {[...pnlRows.expenseAllTime]
                  .sort((a, b) => a.label.localeCompare(b.label))
                  .map((row, idx) => {
                    const ytdMatch = pnlRows.expenseYtd.find(
                      (r) => r.label === row.label,
                    )
                    return (
                      <TableRow key={`expense-${row.label}-${idx}`}>
                        <TableCell className="font-medium capitalize">
                          {row.label}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatAccounting(row.total, kpiCurrency)}
                        </TableCell>
                        <TableCell className="text-right">
                          {formatAccounting(ytdMatch?.total ?? 0, kpiCurrency)}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                {/* Total expenses row (kept negative). */}
                <TableRow className="border-t">
                  <TableCell className="font-bold">Total expenses</TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.totalExpenseAll, kpiCurrency)}
                  </TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.totalExpenseYtd, kpiCurrency)}
                  </TableCell>
                </TableRow>
                {/* Net income row. */}
                <TableRow className="border-t-2">
                  <TableCell className="font-bold">Net income</TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.netIncomeAll, kpiCurrency)}
                  </TableCell>
                  <TableCell className="text-right font-bold">
                    {formatAccounting(pnlRows.netIncomeYtd, kpiCurrency)}
                  </TableCell>
                </TableRow>
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
