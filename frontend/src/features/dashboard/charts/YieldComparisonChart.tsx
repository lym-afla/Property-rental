import { useState } from 'react'
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle } from '@/components/analytics/chartTheme'
import type { PropertyYieldsResponse } from '@/types/analytics'

type Props = {
  data?: PropertyYieldsResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

const yieldSeries = [
  { key: 'gross_yield', label: 'Gross yield', kind: 'yield', visualToken: 'primary' as const },
  { key: 'net_yield', label: 'Net yield', kind: 'yield', visualToken: 'secondary' as const },
] as const
type YieldKey = (typeof yieldSeries)[number]['key']

function yieldState({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load yield comparison.', onRetry }
  if (!data || data.rows.length === 0) return { status: 'empty', message: 'No yield comparison data for this selection.' }
  return { status: 'success' }
}

function statusLabel(status: PropertyYieldsResponse['rows'][number]['status']) {
  return status.replaceAll('_', ' ').replace(/^./, (value) => value.toUpperCase())
}

function formatYield(value: number | null) {
  return value === null ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`
}

export function YieldComparisonChart(props: Props) {
  const { data } = props
  const state = yieldState(props)
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const visibleSeries = yieldSeries.filter((series) => !hiddenKeys.has(series.key))
  const plottedValues = data ? data.rows.flatMap((row) => [row.gross_yield, row.net_yield].filter((value): value is number => value !== null)) : []
  const average = plottedValues.length === 0 ? null : plottedValues.reduce((sum, value) => sum + value, 0) / plottedValues.length
  const table = data ? {
    columns: [
      { key: 'property', label: 'Property' },
      { key: 'gross', label: 'Gross yield', numeric: true },
      { key: 'net', label: 'Net yield', numeric: true },
      { key: 'valuation', label: 'Valuation status' },
    ],
    rows: data.rows.map((row) => ({ property: row.property_name, gross: formatYield(row.gross_yield), net: formatYield(row.net_yield), valuation: statusLabel(row.status) })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Yield comparison"
      subtitle="Gross and net yields are supplied by the yield analytics endpoint."
      controls={state.status === 'success' && <ChartLegend series={yieldSeries} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => { const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next })} />}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis type="number" dataKey="yield" unit="%" name="Yield" />
              <YAxis type="category" dataKey="property_name" name="Property" width={132} />
              {average !== null && <ReferenceLine x={average} stroke="currentColor" strokeDasharray="4 4" label="Average displayed yield" />}
              <Tooltip content={({ active, payload }) => active ? <ChartTooltip label="Property yield" rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatYield(Number(item.value)) }))} /> : null} />
              {visibleSeries.map((series) => {
                const key: YieldKey = series.key
                return (
                <Scatter
                  key={key}
                  name={series.label}
                  fill={chartSeriesStyle(series.visualToken).color}
                  data={data.rows.filter((row) => row[key] !== null).map((row) => ({ property_name: row.property_name, yield: row[key] }))}
                />
                )
              })}
            </ScatterChart>
          </ResponsiveContainer>
          <ul className="sr-only" aria-label="Yield values">
            {data.rows.map((row) => <li key={row.property_id} data-testid={`yield-status-${row.property_id}`}>{row.property_name}: {statusLabel(row.status)}{row.gross_yield !== null && <span data-testid={`yield-point-${row.property_id}-gross`}> Gross {formatYield(row.gross_yield)}</span>}{row.net_yield !== null && <span data-testid={`yield-point-${row.property_id}-net`}> Net {formatYield(row.net_yield)}</span>}</li>)}
          </ul>
        </>
      )}
    </AnalyticsChartCard>
  )
}
