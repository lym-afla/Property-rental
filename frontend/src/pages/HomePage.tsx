import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { format, parseISO, subMonths, subYears } from 'date-fns'

import { useExpenseDrivers, usePortfolioCashFlow, usePortfolioSummary } from '@/api/analytics'
import { useProperties } from '@/api/properties'
import { KpiCard } from '@/components/dashboard/KpiCard'
import { ErrorState } from '@/components/states/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardLayout } from '@/features/dashboard/DashboardLayout'
import { CumulativeCashChart } from '@/features/dashboard/charts/CumulativeCashChart'
import { ExpenseDriversChart } from '@/features/dashboard/charts/ExpenseDriversChart'
import { NetCashFlowChart } from '@/features/dashboard/charts/NetCashFlowChart'
import { RevenueExpenseTrendChart } from '@/features/dashboard/charts/RevenueExpenseTrendChart'
import type { DrillDown } from '@/features/dashboard/charts/chartUtils'
import type { DashboardFilterState, DashboardGrain } from '@/features/dashboard/filters'
import { formatCurrency, formatDate } from '@/lib/format'
import { useSession } from '@/context/SessionProvider'
import type { User } from '@/types/user'

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
  const range = { from: filters.start, to: filters.end }
  const analyticsParams = {
    start: range.from,
    end: range.to,
    currency: filters.currency,
    grain: filters.grain,
    propertyIds: filters.propertyIds,
  }
  const cashFlowQuery = usePortfolioCashFlow(analyticsParams)
  const expenseQuery = useExpenseDrivers(analyticsParams)

  const onDrillDown = ({ from, to, category, currency, propertyIds }: DrillDown) => {
    const params = new URLSearchParams({ from, to, category, currency })
    for (const propertyId of propertyIds) params.append('property', String(propertyId))
    navigate(`/transactions?${params.toString()}`)
  }

  return (
    <div className="space-y-6">
      <PortfolioSummary filters={filters} />

      <NetCashFlowChart data={cashFlowQuery.data} isLoading={cashFlowQuery.isLoading} isError={cashFlowQuery.isError} onRetry={() => { void cashFlowQuery.refetch() }} propertyIds={filters.propertyIds} onDrillDown={onDrillDown} />

      <div className="grid gap-4 lg:grid-cols-2">
        <CumulativeCashChart data={cashFlowQuery.data} isLoading={cashFlowQuery.isLoading} isError={cashFlowQuery.isError} onRetry={() => { void cashFlowQuery.refetch() }} />
        <MigrationPlaceholder
          title="Occupancy migration pending"
          description="Task 9 will restore occupancy using the shared dashboard range and as-of date."
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RevenueExpenseTrendChart data={cashFlowQuery.data} isLoading={cashFlowQuery.isLoading} isError={cashFlowQuery.isError} onRetry={() => { void cashFlowQuery.refetch() }} />
        <MigrationPlaceholder
          title="Currency exposure migration pending"
          description="Task 9 will restore currency exposure using the shared range, currency, properties, and exposure measure."
        />
      </div>

      <ExpenseDriversChart data={expenseQuery.data} isLoading={expenseQuery.isLoading} isError={expenseQuery.isError} onRetry={() => { void expenseQuery.refetch() }} />

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
