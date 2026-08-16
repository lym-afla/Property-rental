import { useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { CHART_AXIS_PROPS, type AnalyticsSeriesDefinition } from '@/components/analytics/chartTheme'
import { useChartTheme } from '@/components/analytics/useChartTheme'
import { formatAccounting, formatCurrency, formatCurrencyAxis, formatDate } from '@/lib/format'
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
    visualToken: (['primary', 'secondary', 'tertiary', 'quaternary'] as const)[index],
  }))
}

function formatPerformanceValue(key: string, value: number | null, currency: string): string {
  return key === 'variance' || key === 'cumulative_arrears'
    ? formatAccounting(value, currency)
    : formatCurrency(value, currency)
}

export function RentPerformanceChart(props: Props) {
  const charts = useChartTheme()
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
      variance: formatPerformanceValue('variance', point.variance, currency),
      cumulative_arrears: formatPerformanceValue('cumulative_arrears', point.cumulative_arrears, currency),
      status: point.status.replaceAll('_', ' '),
    })),
  }

  return (
    <AnalyticsChartCard
      state={state}
      title="Tenant rent performance"
      subtitle={data ? `Native currency: ${data.currency} · Reporting period: ${data.start} to ${data.end}` : 'Expected, received, variance, and cumulative arrears supplied by the server.'}
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
      {state.status === 'success' && data && <div className="flex h-full min-h-0 flex-col">
        <span className="sr-only">Expected rent is a line, received rent is bars, and variance is signed against the zero baseline.</span>
        <div className="min-h-0 flex-1">
          <ResponsiveChartContainer width="100%" height="100%">
            <ComposedChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="period_start" tickFormatter={formatDate} minTickGap={24} {...CHART_AXIS_PROPS} />
              <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), currency)} {...CHART_AXIS_PROPS} />
              <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatPerformanceValue(String(item.dataKey), typeof item.value === 'number' ? item.value : null, currency) }))} /> : null} />
              <ReferenceLine y={0} stroke="currentColor" aria-label="Variance zero baseline" />
              {visibleSeries.filter((item) => item.key === 'received' || item.key === 'variance').map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} fill={charts.style(item.visualToken).color} stroke={charts.style(item.visualToken).color} />)}
              {visibleSeries.filter((item) => item.key === 'expected' || item.key === 'cumulative_arrears').map((item) => <Line key={item.key} type="monotone" dataKey={item.key} name={item.label} stroke={charts.style(item.visualToken).color} strokeWidth={charts.style(item.visualToken).strokeWidth} dot={false} activeDot={false} />)}
            </ComposedChart>
          </ResponsiveChartContainer>
        </div>
      </div>}
    </AnalyticsChartCard>
  )
}
