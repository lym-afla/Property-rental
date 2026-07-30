import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartVisualTokens } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'

import { chartState, type ChartDataProps } from './chartUtils'

export function ExpenseDriversChart({ data, isLoading, isError, onRetry }: ChartDataProps) {
  const rows = data ? data.series
    .filter((item) => item.kind === 'expense_category')
    .map((item) => ({ key: item.key, category: item.label, total: Math.abs(data.points.reduce((sum, point) => sum + Number(point[item.key] ?? 0), 0)) }))
    .filter((row) => row.total > 0)
    .sort((left, right) => right.total - left.total)
    .map((row, index) => ({ ...row, rank: index + 1 })) : []
  const state = chartState('Expense drivers', { data, isLoading, isError, onRetry }, rows.length > 0)
  const table = state.status === 'success' && data ? { columns: [{ key: 'rank', label: 'Rank', numeric: true }, { key: 'category', label: 'Expense category' }, { key: 'total', label: 'Total', numeric: true }], rows: rows.map((row) => ({ rank: row.rank, category: row.category, total: formatCurrency(row.total, data.currency ?? '') })) } : undefined
  return (
    <AnalyticsChartCard state={state} title="Expense drivers" subtitle="Ranked spend categories supplied by the expense analytics endpoint." table={table}>
      {state.status === 'success' && data && <>
        <ResponsiveChartContainer width="100%" height="100%"><BarChart data={rows} layout="vertical" margin={{ top: 8, right: 12, left: 28, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} />
          <YAxis type="category" dataKey="category" width={132} tick={{ fontSize: 12 }} />
          <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={String(label)} rows={(payload ?? []).map((item) => ({ label: 'Total', value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
          <Bar dataKey="total" name="Total spend" fill={chartVisualTokens.secondary.color} />
        </BarChart></ResponsiveChartContainer>
        <ol className="sr-only" aria-label="Ranked expense drivers">{rows.map((row) => <li key={row.key} data-testid={`expense-driver-${row.key}`} data-rank={row.rank}>{row.rank}. {row.category}: {formatCurrency(row.total, data.currency ?? '')}</li>)}</ol>
      </>}
    </AnalyticsChartCard>
  )
}
