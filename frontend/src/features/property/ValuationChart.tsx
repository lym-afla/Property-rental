import { useState } from 'react'
import { parseISO } from 'date-fns'
import { Bar, CartesianGrid, ComposedChart, Line, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle, type AnalyticsSeriesDefinition } from '@/components/analytics/chartTheme'
import { Button } from '@/components/ui/button'
import { formatAccounting, formatCurrencyAxis, formatDate } from '@/lib/format'
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

function paddedTimeDomain(points: readonly { timestamp: number }[]) {
  if (points.length === 0) return ['dataMin', 'dataMax'] as const
  const values = points.map((point) => point.timestamp)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, 1000 * 60 * 60 * 24 * 30)
  const padding = span * 0.04
  return [min - padding, max + padding] as [number, number]
}

export function ValuationChart(props: Props) {
  const { data } = props
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const state = stateFor(props)
  const series = valuationSeries(data)
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const currency = data?.currency ?? ''
  const chartPoints = data?.points.map((point) => ({
    ...point,
    timestamp: parseISO(point.period_start).getTime(),
  })) ?? []
  const table = data && {
    columns: [
      { key: 'period', label: 'Record date' },
      { key: 'status', label: 'Status' },
      ...series.map((item) => ({ key: item.key, label: item.label, numeric: true })),
    ],
    rows: data.points.map((point) => ({
      period: formatDate(point.period_start),
      status: point.status,
      total_value: formatAccounting(point.total_value, currency),
      debt: formatAccounting(point.debt, currency),
      equity: formatAccounting(point.equity, currency),
    })),
  }

  return (
    <AnalyticsChartCard
      state={state}
      title="Property valuation"
      subtitle={data ? `All time: ${data.start} to ${data.end}` : undefined}
      controls={state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current)
        if (next.has(key)) {
          next.delete(key)
        } else {
          next.add(key)
        }
        return next
      })} />}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && <ResponsiveChartContainer width="100%" height="100%">
        <ComposedChart data={chartPoints} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="timestamp"
            type="number"
            scale="time"
            domain={paddedTimeDomain(chartPoints)}
            tickFormatter={(value) => formatDate(new Date(Number(value)))}
            minTickGap={24}
          />
          <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), currency)} />
          <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(new Date(Number(label)))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatAccounting(typeof item.value === 'number' ? item.value : null, currency) }))} /> : null} />
          {visibleSeries.filter((item) => item.key !== 'total_value').map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} stackId="valuation" fill={chartSeriesStyle(item.visualToken).color} stroke={chartSeriesStyle(item.visualToken).color} />)}
          {visibleSeries.filter((item) => item.key === 'total_value').map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={chartSeriesStyle(item.visualToken).color} strokeWidth={chartSeriesStyle(item.visualToken).strokeWidth} dot={false} />)}
        </ComposedChart>
      </ResponsiveChartContainer>}
    </AnalyticsChartCard>
  )
}
