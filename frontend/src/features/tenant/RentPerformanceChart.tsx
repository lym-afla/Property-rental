import { useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle, type AnalyticsSeriesDefinition } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis, formatDate } from '@/lib/format'
import type { TenantRentPerformanceResponse } from '@/types/analytics'

type Props = {
  data?: TenantRentPerformanceResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

function stateFor({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load tenant rent performance.', onRetry }
  if (!data || data.points.length === 0) return { status: 'empty', message: 'No tenant rent-performance data for this selection.' }
  return { status: 'success' }
}

function performanceSeries(data?: TenantRentPerformanceResponse): AnalyticsSeriesDefinition[] {
  if (!data) return []
  return data.series.map((series, index) => ({
    ...series,
    visualToken: (['primary', 'secondary', 'tertiary', 'default'] as const)[index],
  }))
}

function formatSignedCurrency(value: number | null, currency: string): string {
  if (value === null) return '—'
  return `${value < 0 ? '-' : ''}${formatCurrency(Math.abs(value), currency)}`
}

export function RentPerformanceChart(props: Props) {
  const { data } = props
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const state = stateFor(props)
  const series = performanceSeries(data)
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const currency = data?.currency ?? ''
  const table = data && {
    columns: [
      { key: 'period', label: 'Period' },
      ...series.map((item) => ({ key: item.key, label: item.label, numeric: true })),
      { key: 'status', label: 'Status' },
    ],
    rows: data.points.map((point) => ({
      period: `${formatDate(point.period_start)} to ${formatDate(point.period_end)}`,
      expected: formatCurrency(point.expected, currency),
      received: formatCurrency(point.received, currency),
      variance: formatSignedCurrency(point.variance, currency),
      cumulative_arrears: formatCurrency(point.cumulative_arrears, currency),
      status: point.status.replaceAll('_', ' '),
    })),
  }

  return (
    <AnalyticsChartCard
      state={state}
      title="Tenant rent performance"
      subtitle={data ? `Reporting period: ${data.start} to ${data.end}` : 'Expected, received, variance, and cumulative arrears supplied by the server.'}
      controls={state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current)
        next.has(key) ? next.delete(key) : next.add(key)
        return next
      })} />}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && <div className="flex h-full min-h-0 flex-col">
        <span className="sr-only">Expected rent is a line, received rent is bars, and variance is signed against the zero baseline.</span>
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="period_start" tickFormatter={formatDate} minTickGap={24} />
              <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), currency)} />
              <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(typeof item.value === 'number' ? item.value : null, currency) }))} /> : null} />
              <ReferenceLine y={0} stroke="currentColor" aria-label="Variance zero baseline" />
              {visibleSeries.filter((item) => item.key === 'received' || item.key === 'variance').map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} fill={chartSeriesStyle(item.visualToken).color} />)}
              {visibleSeries.filter((item) => item.key === 'expected' || item.key === 'cumulative_arrears').map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={chartSeriesStyle(item.visualToken).color} strokeWidth={2.5} dot />)}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>}
    </AnalyticsChartCard>
  )
}
