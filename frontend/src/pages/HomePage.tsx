// Responsive investment dashboard shell. URL-owned global filters feed the
// validated analytics summary and the compatible legacy chart-data requests.
// The legacy charts and detailed P&L remain below the new summary until their
// dedicated redesign tasks migrate them to the typed analytics endpoints.
//
// Drill-down: clicking a Cash Flow bar segment navigates to
// /transactions?from=...&to=...&category=... for the period + category.
// `periodLabelToRange` translates the chart's period label (`Jan-24`,
// `Q1 24`, `2024`) into a `YYYY-MM-DD` range that the TransactionsPage
// filter already understands (it reads `from`/`to`/`category` from the URL
// query string).
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { format, parseISO, subMonths, subYears } from 'date-fns'

import { usePortfolioSummary } from '@/api/analytics'
import { useChartData } from '@/api/charts'
import { useProperties, usePropertiesWithStats } from '@/api/properties'
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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/features/dashboard/DashboardLayout'
import type { DashboardFilterState, DashboardGrain } from '@/features/dashboard/filters'
import { formatAccounting, formatCurrency, formatDate } from '@/lib/format'
import { useSession } from '@/context/SessionProvider'
import type { User } from '@/types/user'

type Frequency = 'M' | 'Q' | 'Y'

const GRAIN_TO_FREQUENCY: Record<DashboardGrain, Frequency> = {
  month: 'M',
  quarter: 'Q',
  year: 'Y',
}

function timelineStart(end: string, timeline: string): string {
  if (timeline === 'All') return '1900-01-01'
  const endDate = parseISO(end)
  switch (timeline) {
    case 'YTD':
      return `${end.slice(0, 4)}-01-01`
    case '3m':
      return format(subMonths(endDate, 3), 'yyyy-MM-dd')
    case '12m':
      return format(subYears(endDate, 1), 'yyyy-MM-dd')
    case '3Y':
      return format(subYears(endDate, 3), 'yyyy-MM-dd')
    case '5Y':
      return format(subYears(endDate, 5), 'yyyy-MM-dd')
    case '6m':
    default:
      return format(subMonths(endDate, 6), 'yyyy-MM-dd')
  }
}

function dashboardDefaults(user: User | null): DashboardFilterState {
  const end = user?.effective_date ?? new Date().toISOString().slice(0, 10)
  const currencies = ['USD', 'EUR', 'GBP', 'RUB'] as const
  const userCurrency = user?.default_currency?.toUpperCase()
  const currency = currencies.find((value) => value === userCurrency) ?? 'USD'
  const grain: DashboardGrain = user?.chart_frequency === 'Q'
    ? 'quarter'
    : user?.chart_frequency === 'Y'
      ? 'year'
      : 'month'
  return {
    section: 'overview',
    start: timelineStart(end, user?.chart_timeline ?? '6m'),
    end,
    currency,
    grain,
    comparison: null,
    propertyIds: [],
    exposureMeasure: 'property_value',
  }
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
  const { user } = useSession()
  const properties = useProperties()
  const defaults = useMemo(() => dashboardDefaults(user), [user])

  return (
    <DashboardLayout
      defaults={defaults}
      properties={(properties.data ?? []).map(({ id, name }) => ({ id, name }))}
    >
      {(filters) => <DashboardContent filters={filters} />}
    </DashboardLayout>
  )
}

function DashboardContent({ filters }: { filters: DashboardFilterState }) {
  const navigate = useNavigate()
  const userCurrency = filters.currency
  const frequency = GRAIN_TO_FREQUENCY[filters.grain]
  const range = { from: filters.start, to: filters.end }

  // ---- Data hooks ----------------------------------------------------------
  // The legacy P&L still uses property stats; scope it to the shared as-of
  // date and currency while the validated summary owns the KPI semantics.
  const propertiesStats = usePropertiesWithStats(filters.end, userCurrency)

  // One chart-data request for the headline bar chart; the same response
  // powers both Cash Flow and (via Net Income Trend's client-side sum) the
  // net income trajectory, so a single round-trip feeds two tiles.
  const chartQuery = useChartData({
    type: 'homePage',
    frequency,
    start: range.from,
    end: range.to,
    currency: userCurrency,
  })
  // Keep separate query handles for the legacy components. Identical keys
  // deduplicate at the query-client boundary.
  const expenseQuery = useChartData({
    type: 'homePage',
    frequency,
    start: range.from,
    end: range.to,
    currency: userCurrency,
  })
  const netIncomeQuery = useChartData({
    type: 'homePage',
    frequency,
    start: range.from,
    end: range.to,
    currency: userCurrency,
  })
  const kpiCurrency = userCurrency

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
  // YTD window: Jan 1 through the shared as-of date.
  const today = new Date(`${filters.end}T12:00:00.000Z`)
  const todayIso = filters.end
  const yearStart = `${today.getUTCFullYear()}-01-01`
  const yearEnd = filters.end
  const pnlAllTimeQuery = useChartData({
    type: 'homePage',
    frequency: 'Y',
    start: '1900-01-01',
    end: todayIso,
    currency: userCurrency,
  })
  const pnlYtdQuery = useChartData({
    type: 'homePage',
    frequency: 'Y',
    start: yearStart,
    end: yearEnd,
    currency: userCurrency,
  })

  // Income vs expense classification — mirrors `rentals/constants.py`.
  // Only `rent` is income; `cost_reimbursement` (formerly `other_income`)
  // is an expense-category offset (positive amount that nets against the
  // other expense categories), so it lives on the expense side.
  const INCOME_CATEGORIES = ['rent']

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
      // T12: filter out categories with zero total so empty buckets (e.g.
      // a category that exists in the choices but has no transactions in
      // the window) don't appear as a stray row in the P&L.
      return rows.filter((r) => r.total !== 0)
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
  // Legacy charts own their loading state; this guard is for the P&L table.
  const isLoading = propertiesStats.isLoading
  const isError = propertiesStats.isError

  return (
    <div className="space-y-6">
      <PortfolioSummary filters={filters} />

      {/* ---- Cash Flow (full-width) ------------------------------------- */}
      {/* The chart itself owns its loading state via ChartCard; we just
          pass the data through and let the controls live in the card
          header so they're co-located with the chart they affect. */}
      <CashFlowChart
        data={chartQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        onBarClick={onBarClick}
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
          data={netIncomeQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        />
        <CurrencyExposureChart />
      </div>

      {/* ---- P&L table -------------------------------------------------- */}
      {/* Per-category P&L breakdown with All-time + YTD columns. The chart-data
          request gives us one dataset per category; we sum each one to get
          the totals displayed here. Currency follows the user's
          `default_currency` (`kpiCurrency`): both chart-data requests below
          pass `currency: userCurrency`, and `kpiCurrency` resolves to the
          user's display currency (falling back to USD only when the session
          has not loaded yet or the user never picked one). Layout:
          income categories first, then "Total revenue", then expense
          categories (alphabetical, kept negative), then "Total expenses"
          and "Net income". `formatAccounting` renders negatives as
          `$(-1,234)` so the sign convention is unambiguous. */}
      <Card>
        <CardHeader>
          <CardTitle>Profit &amp; Loss</CardTitle>
          <p className="text-xs text-muted-foreground">
            All values in {kpiCurrency}, your display currency. Per-category
            breakdown across all owned properties, FX-converted on the backend.
          </p>
        </CardHeader>
        <CardContent>
          {isError ? (
            <ErrorState
              message="Failed to load property stats"
              onRetry={() => {
                propertiesStats.refetch()
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
        Dashboard timeline {filters.grain} ({formatDate(range.from)} to {formatDate(range.to)})
      </span>
    </div>
  )
}

function PortfolioSummary({ filters }: { filters: DashboardFilterState }) {
  const summary = usePortfolioSummary({
    start: filters.start,
    end: filters.end,
    currency: filters.currency,
    grain: filters.grain,
    comparison: filters.comparison,
    propertyIds: filters.propertyIds,
  })

  if (summary.isError) {
    return (
      <ErrorState
        message="Failed to load portfolio summary"
        onRetry={() => summary.refetch()}
      />
    )
  }

  if (summary.isLoading || !summary.data) {
    return (
      <div aria-label="Loading portfolio summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => (
          <Skeleton key={index} className="h-28 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  if (summary.data.property_count === 0) {
    return (
      <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
        No portfolio data for this selection.
      </div>
    )
  }

  const data = summary.data
  const money = (value: number | null) => (
    <span className="tabular-nums">{formatCurrency(value, data.currency)}</span>
  )
  return (
    <div aria-label="Portfolio summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
      <KpiCard label="Portfolio value" value={money(data.property_value)} description="Latest covered valuations" />
      <KpiCard label="Debt" value={money(data.debt)} description="As of selected date" />
      <KpiCard label="Equity" value={money(data.equity)} description="Value less debt" />
      <KpiCard label="Revenue" value={money(data.revenue)} description="Selected period" />
      <KpiCard label="Net income" value={money(data.net_income)} description="Selected period" />
      <KpiCard
        label="Occupancy"
        value={<span className="tabular-nums">{data.occupancy_rate}%</span>}
        description={`${data.occupied} of ${data.rental_inventory_count} rental units`}
      />
    </div>
  )
}
