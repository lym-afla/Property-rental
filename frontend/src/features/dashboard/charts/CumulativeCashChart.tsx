import { Area, AreaChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { CHART_AXIS_PROPS } from '@/components/analytics/chartTheme'
import { useChartTheme } from '@/components/analytics/useChartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'

import { cashTable, chartState, compactPeriod, hasSeriesValues, type ChartDataProps } from './chartUtils'

export function CumulativeCashChart({ data, isLoading, isError, onRetry }: ChartDataProps) {
  const charts = useChartTheme()
  const series = data?.series.filter((item) => item.kind === 'cumulative') ?? []
  const cumulativeSeries = series.at(0)
  const state = chartState('Cumulative cash', { data, isLoading, isError, onRetry }, hasSeriesValues(data, series))
  const last = cumulativeSeries && data?.points.at(-1)?.[cumulativeSeries.key] as number | null | undefined
  return (
    <AnalyticsChartCard
      state={state}
      title="Cumulative cash"
      subtitle="Running net cash from the server-provided cumulative series."
      summary={state.status === 'success' && data && last !== undefined ? <p className="font-medium">Final cumulative cash: {formatCurrency(last, data.currency ?? '')}</p> : undefined}
      table={state.status === 'success' && data ? cashTable(data, series) : undefined}
    >
      {state.status === 'success' && data && cumulativeSeries && <ResponsiveChartContainer width="100%" height="100%"><AreaChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="period_start" tickFormatter={compactPeriod} minTickGap={24} {...CHART_AXIS_PROPS} />
        <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} {...CHART_AXIS_PROPS} />
        <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={compactPeriod(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
        <ReferenceLine y={0} stroke="currentColor" />
        <Area type="monotone" dataKey={cumulativeSeries.key} name={cumulativeSeries.label} stroke={charts.style('primary').color} fill={charts.style('primary').color} fillOpacity={0.15} />
      </AreaChart></ResponsiveChartContainer>}
    </AnalyticsChartCard>
  )
}
