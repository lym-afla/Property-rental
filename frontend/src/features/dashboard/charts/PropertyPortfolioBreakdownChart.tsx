import { useState } from 'react'
import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { CHART_AXIS_PROPS } from '@/components/analytics/chartTheme'
import { useChartTheme } from '@/components/analytics/useChartTheme'
import { PROPERTY_BREAKDOWN_MEASURES, type DashboardPropertyBreakdownMeasure } from '@/features/dashboard/filters'
import { formatCurrency, formatCurrencyAxis, formatDate } from '@/lib/format'
import type { PropertyBreakdownMeasure } from '@/types/analytics'

type PropertyBreakdownData = {
  currency?: string
  measure: PropertyBreakdownMeasure
  measure_label: string
  series: Array<{ key: string; label: string; kind: string }>
  points: Array<{ period_start: string; period_end: string; [key: string]: string | number | null }>
}

type Props = {
  data?: PropertyBreakdownData
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
  measure: DashboardPropertyBreakdownMeasure
  onMeasureChange: (measure: DashboardPropertyBreakdownMeasure) => void
}

const MEASURE_LABELS: Record<DashboardPropertyBreakdownMeasure, string> = {
  property_value: 'Property value', equity: 'Equity', debt: 'Debt', rental_income: 'Rental income',
}

function breakdownState({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load property portfolio breakdown.', onRetry }
  if (!data || data.points.length === 0 || data.series.length === 0) return { status: 'empty', message: 'No property portfolio data for this selection.' }
  return { status: 'success' }
}

function timestamp(value: string) {
  return Date.parse(`${value}T00:00:00Z`)
}

export function PropertyPortfolioBreakdownChart(props: Props) {
  const charts = useChartTheme()
  const { data, measure, onMeasureChange } = props
  const state = breakdownState(props)
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const series = data?.series.map((item, index) => ({ ...item, color: charts.color(index) })) ?? []
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const chartPoints = data?.points.map((point) => ({ ...point, period: timestamp(point.period_start) })) ?? []
  const rows = data ? data.points.flatMap((point) => series.filter((item) => Object.hasOwn(point, item.key)).map((item) => ({
    id: `${point.period_start}-${item.key}`,
    period: point.period_start,
    property: item.label,
    value: point[item.key] as number | null | undefined,
  }))) : []
  const table = data ? {
    columns: [{ key: 'period', label: 'Period' }, { key: 'property', label: 'Property' }, { key: 'value', label: data.measure_label, numeric: true }],
    rows: rows.map((row) => ({ period: formatDate(row.period), property: row.property, value: formatCurrency(row.value, data.currency ?? '') })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Portfolio breakdown by property"
      subtitle={data ? `${data.measure_label} by property in ${data.currency}.` : 'Reporting values grouped by property.'}
      controls={<><label className="sr-only" htmlFor="property-breakdown-measure">Portfolio breakdown measure</label><select id="property-breakdown-measure" aria-label="Portfolio breakdown measure" className="min-h-11 rounded-md border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50" value={measure} onChange={(event) => onMeasureChange(event.target.value as DashboardPropertyBreakdownMeasure)}>{PROPERTY_BREAKDOWN_MEASURES.map((option) => <option key={option} value={option}>{MEASURE_LABELS[option]}</option>)}</select>{state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next })} resolveStyle={(item) => ({ ...charts.style(), color: series.find((candidate) => candidate.key === item.key)?.color ?? charts.style().color })} />}</>}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <div className="h-full overflow-x-auto">
          <div data-testid="property-breakdown-plot" className="h-full min-w-[320px]">
            <ResponsiveChartContainer width="100%" height="100%">
              <LineChart data={chartPoints} margin={{ top: 8, right: 12, left: 12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="period" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={(value) => formatDate(new Date(Number(value)))} {...CHART_AXIS_PROPS} />
                <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} width={72} {...CHART_AXIS_PROPS} />
                <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(new Date(Number(label)))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
                {visibleSeries.map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={item.color} strokeWidth={charts.style().strokeWidth} dot={false} activeDot={false} connectNulls={false} />)}
              </LineChart>
            </ResponsiveChartContainer>
          </div>
        </div>
      )}
    </AnalyticsChartCard>
  )
}
