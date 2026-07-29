// Responsive investment dashboard shell. URL-owned global filters feed the
// validated analytics summary and the compatible legacy chart-data requests.
// Compatible legacy charts remain below the new summary until their dedicated
// redesign tasks migrate them to the typed analytics endpoints.
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
import { useProperties } from '@/api/properties'
import { CashFlowChart } from '@/components/charts/CashFlowChart'
import { ExpenseBreakdownChart } from '@/components/charts/ExpenseBreakdownChart'
import { NetIncomeTrendChart } from '@/components/charts/NetIncomeTrendChart'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { ErrorState } from '@/components/states/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/features/dashboard/DashboardLayout'
import type { DashboardFilterState, DashboardGrain } from '@/features/dashboard/filters'
import { formatCurrency, formatDate } from '@/lib/format'
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

  if (filters.propertyIds.length > 0) {
    return (
      <div className="space-y-6">
        <PortfolioSummary filters={filters} />
        <MigrationPlaceholder
          title="Property-scoped chart migration pending"
          description="Tasks 8–9 will restore charts here using analytics endpoints that honor the selected properties. The legacy all-property charts are hidden so they cannot contradict the shared filter."
        />
      </div>
    )
  }

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
        <MigrationPlaceholder
          title="Occupancy migration pending"
          description="Task 8 will restore occupancy using the shared dashboard range and as-of date."
        />
      </div>

      {/* ---- Net income trend + Currency exposure (side-by-side) -------- */}
      <div className="grid gap-4 lg:grid-cols-2">
        <NetIncomeTrendChart
          data={netIncomeQuery.data ?? { labels: [], datasets: [], currency: kpiCurrency }}
        />
        <MigrationPlaceholder
          title="Currency exposure migration pending"
          description="Task 9 will restore currency exposure using the shared range, currency, properties, and exposure measure."
        />
      </div>

      <MigrationPlaceholder
        title="Profit & Loss migration pending"
        description="Task 8 will restore the detailed P&L using the shared range, currency, and property selection."
      />

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
        value={
          <span className="tabular-nums">
            {data.occupancy_rate.toLocaleString(undefined, { maximumFractionDigits: 1 })}%
          </span>
        }
        description={`${data.occupied} of ${data.rental_inventory_count} rental units`}
      />
    </div>
  )
}

function MigrationPlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <Card className="min-h-52 border-dashed">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}
