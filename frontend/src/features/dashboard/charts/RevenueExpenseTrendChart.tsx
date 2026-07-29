import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'

import { cashTable, chartState, compactPeriod, hasSeriesValues, seriesWithVisualTokens, type ChartDataProps } from './chartUtils'

const TREND_KINDS = new Set(['income_total', 'expense_total'])

export function RevenueExpenseTrendChart({ data, isLoading, isError, onRetry }: ChartDataProps) {
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const series = data ? seriesWithVisualTokens(data.series.filter((item) => TREND_KINDS.has(item.kind))) : []
  const state = chartState('Revenue and expenses', { data, isLoading, isError, onRetry }, hasSeriesValues(data, series))
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  return (
    <AnalyticsChartCard state={state} title="Revenue and expenses" subtitle="Server-provided income and expense series by period." controls={state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => { const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next })} />} table={state.status === 'success' && data ? cashTable(data, series) : undefined}>
      {state.status === 'success' && data && <ResponsiveContainer width="100%" height="100%"><LineChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="period_start" tickFormatter={compactPeriod} minTickGap={24} />
        <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} />
        <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={compactPeriod(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
        {visibleSeries.map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={chartSeriesStyle(item.visualToken).color} strokeDasharray={chartSeriesStyle(item.visualToken).strokeDasharray} strokeWidth={2.5} dot={false} />)}
      </LineChart></ResponsiveContainer>}
    </AnalyticsChartCard>
  )
}
