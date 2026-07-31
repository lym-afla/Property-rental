import { CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartVisualTokens } from '@/components/analytics/chartTheme'
import { formatDate } from '@/lib/format'
import type { PortfolioOccupancyResponse } from '@/types/analytics'

type Props = {
  data?: PortfolioOccupancyResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

function occupancyState({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load occupancy risk.', onRetry }
  if (!data || data.points.length === 0) return { status: 'empty', message: 'No occupancy risk data for this selection.' }
  return { status: 'success' }
}

function formatRate(value: number | null | undefined) {
  return typeof value === 'number' ? `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%` : '—'
}

export function OccupancyRiskChart(props: Props) {
  const { data } = props
  const state = occupancyState(props)
  const points = data?.points ?? []
  const table = data ? {
    columns: [{ key: 'period', label: 'Period' }, { key: 'occupancy', label: 'Occupancy', numeric: true }, { key: 'occupied', label: 'Occupied', numeric: true }, { key: 'vacant', label: 'Vacant', numeric: true }, { key: 'capacity', label: 'Capacity', numeric: true }],
    rows: points.map((point) => ({ period: formatDate(point.period_start), occupancy: formatRate(point.occupancy_rate as number | null), occupied: point.occupied ?? '—', vacant: point.vacant ?? '—', capacity: point.capacity ?? '—' })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Occupancy risk"
      subtitle="Stepped occupancy rate by reporting period."
      summary={state.status === 'success' && <p className="text-sm text-muted-foreground">Vacant and capacity context is supplied by the occupancy endpoint.</p>}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <>
          <ResponsiveChartContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis dataKey="period_start" tickFormatter={formatDate} minTickGap={24} />
              <YAxis domain={[0, 100]} allowDataOverflow unit="%" />
              <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={formatDate(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatRate(item.value as number) }))} /> : null} />
              <Line type="stepAfter" dataKey="occupancy_rate" name="Occupancy rate" stroke={chartVisualTokens.primary.color} strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveChartContainer>
          <ul className="sr-only" aria-label="Occupancy risk values">{points.map((point) => <li key={point.period_start} data-testid={`occupancy-rate-${point.period_start}`} data-rate={point.occupancy_rate}>{formatDate(point.period_start)}: {formatRate(point.occupancy_rate as number | null)}, occupied {point.occupied}, vacant {point.vacant}, capacity {point.capacity}</li>)}</ul>
        </>
      )}
    </AnalyticsChartCard>
  )
}
