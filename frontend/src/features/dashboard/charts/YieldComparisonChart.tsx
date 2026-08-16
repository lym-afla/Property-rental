import { useState } from 'react'
import { CartesianGrid, ReferenceLine, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { FinancialDefinitions } from '@/components/analytics/FinancialDefinitions'
import { CHART_AXIS_PROPS } from '@/components/analytics/chartTheme'
import { useChartTheme } from '@/components/analytics/useChartTheme'
import type { PropertyYieldsResponse } from '@/types/analytics'

import { yieldTooltipRows } from './yieldTooltipRows'

type Props = {
  data?: PropertyYieldsResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

const yieldSeries = [
  { key: 'gross_yield', label: 'Gross yield', kind: 'yield', visualToken: 'primary' as const },
  { key: 'equity_yield', label: 'Equity yield', kind: 'yield', visualToken: 'secondary' as const },
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

function formatYield(value: unknown) {
  return !isFiniteNumber(value) ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function unavailableYieldMessage(row: PropertyYieldsResponse['rows'][number]) {
  const grossAvailable = isFiniteNumber(row.gross_yield)
  const equityAvailable = isFiniteNumber(row.equity_yield)
  if (!grossAvailable && !equityAvailable) return 'no yield plotted'
  if (!grossAvailable) return 'gross yield not plotted'
  if (!equityAvailable) return 'equity yield not plotted'
  return null
}

export function YieldComparisonChart(props: Props) {
  const charts = useChartTheme()
  const { data } = props
  const state = yieldState(props)
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const visibleSeries = yieldSeries.filter((series) => !hiddenKeys.has(series.key))
  const missingValuations = data?.rows.filter((row) => row.status === 'missing_valuation') ?? []
  const plottedValues = data ? data.rows.flatMap((row) => [row.gross_yield, row.equity_yield].filter(isFiniteNumber)) : []
  const average = plottedValues.length === 0 ? null : plottedValues.reduce((sum, value) => sum + value, 0) / plottedValues.length
  const table = data ? {
    columns: [
      { key: 'property', label: 'Property' },
      { key: 'gross', label: 'Gross yield', numeric: true },
      { key: 'equity', label: 'Equity yield', numeric: true },
      { key: 'valuation', label: 'Valuation status' },
    ],
    rows: data.rows.map((row) => ({ property: row.property_name, gross: formatYield(row.gross_yield), equity: formatYield(row.equity_yield), valuation: statusLabel(row.status) })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Yield comparison"
      subtitle="Gross and equity yields are supplied by the yield analytics endpoint."
      controls={<><FinancialDefinitions />{state.status === 'success' && <ChartLegend series={yieldSeries} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current)
        if (next.has(key)) {
          next.delete(key)
        } else {
          next.add(key)
        }
        return next
      })} />}</>}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <>
          <div className="flex h-full min-h-0 flex-col gap-2">
            <div className="min-h-0 flex-1">
              <ResponsiveChartContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" dataKey="yield" unit="%" name="Yield" {...CHART_AXIS_PROPS} />
                  <YAxis type="category" dataKey="property_name" name="Property" width={132} {...CHART_AXIS_PROPS} />
                  {average !== null && <ReferenceLine x={average} stroke="currentColor" strokeDasharray="4 4" label="Average displayed yield" />}
                  <Tooltip content={({ active, payload }) => {
                    const propertyName = payload?.find((item) => typeof item.payload?.property_name === 'string')?.payload?.property_name
                    const rows = yieldTooltipRows(payload ?? [])
                    return active && propertyName ? <ChartTooltip label={propertyName} rows={rows} /> : null
                  }} />
                  {visibleSeries.map((series) => {
                    const key: YieldKey = series.key
                    return <Scatter key={key} name={series.label} fill={charts.style(series.visualToken).color} data={data.rows.flatMap((row) => isFiniteNumber(row[key]) ? [{ property_name: row.property_name, yield: row[key] }] : [])} />
                  })}
                </ScatterChart>
              </ResponsiveChartContainer>
            </div>
            {missingValuations.length > 0 && <div data-testid="missing-valuation-callout" className="rounded-md border border-dashed px-3 py-2 text-sm"><p className="font-medium">Missing valuation</p><ul className="list-disc pl-5">{missingValuations.map((row) => <li key={row.property_id}>{row.property_name}: {unavailableYieldMessage(row)}</li>)}</ul></div>}
          </div>
          <ul className="sr-only" aria-label="Yield values">
            {data.rows.map((row) => <li key={row.property_id} data-testid={`yield-status-${row.property_id}`}>{row.property_name}: {statusLabel(row.status)}{isFiniteNumber(row.gross_yield) && <span data-testid={`yield-point-${row.property_id}-gross`}> Gross {formatYield(row.gross_yield)}</span>}{isFiniteNumber(row.equity_yield) && <span data-testid={`yield-point-${row.property_id}-equity`}> Equity {formatYield(row.equity_yield)}</span>}</li>)}
          </ul>
        </>
      )}
    </AnalyticsChartCard>
  )
}
