import { useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle, type AnalyticsSeriesDefinition } from '@/components/analytics/chartTheme'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatCurrencyAxis, formatDate } from '@/lib/format'
import type { PropertyValuationAnalyticsResponse } from '@/types/analytics'

type Props = {
  data?: PropertyValuationAnalyticsResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
  onViewHistory?: () => void
}

function stateFor({ data, isLoading, isError, onRetry, onViewHistory }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load property valuation.', onRetry }
  if (!data || data.points.length === 0) {
    return {
      status: 'empty',
      message: 'No valuation records are available yet.',
      action: onViewHistory && <Button className="min-h-11" onClick={onViewHistory}>View valuation history</Button>,
    }
  }
  return { status: 'success' }
}

function valuationSeries(data?: PropertyValuationAnalyticsResponse): AnalyticsSeriesDefinition[] {
  if (!data) return []
  return data.series.map((series, index) => ({
    ...series,
    visualToken: (['primary', 'secondary', 'tertiary'] as const)[index],
  }))
}

export function ValuationChart(props: Props) {
  const { data } = props
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const state = stateFor(props)
  const series = valuationSeries(data)
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const currency = data?.currency ?? ''
  const table = data && {
    columns: [
      { key: 'period', label: 'Record date' },
      ...series.map((item) => ({ key: item.key, label: item.label, numeric: true })),
    ],
    rows: data.points.map((point) => ({
      period: formatDate(point.period_start),
      total_value: formatCurrency(point.total_value, currency),
      debt: formatCurrency(point.debt, currency),
      equity: formatCurrency(point.equity, currency),
    })),
  }

  return (
    <AnalyticsChartCard
      state={state}
      title="Property valuation"
      subtitle={data
        ? `All time: ${data.start} to ${data.end}. Server-provided valuation records; no client-side time cutoff.`
        : 'Server-provided valuation records; no client-side time cutoff.'}
      controls={state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current)
        next.has(key) ? next.delete(key) : next.add(key)
        return next
      })} />}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="period_start" tickFormatter={formatDate} minTickGap={24} />
          <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), currency)} />
          <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(typeof item.value === 'number' ? item.value : null, currency) }))} /> : null} />
          {visibleSeries.filter((item) => item.key !== 'total_value').map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} stackId="valuation" fill={chartSeriesStyle(item.visualToken).color} />)}
          {visibleSeries.filter((item) => item.key === 'total_value').map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={chartSeriesStyle(item.visualToken).color} strokeWidth={2.5} dot />)}
        </ComposedChart>
      </ResponsiveContainer>}
    </AnalyticsChartCard>
  )
}
