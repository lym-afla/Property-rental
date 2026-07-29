import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle } from '@/components/analytics/chartTheme'
import { EXPOSURE_MEASURES, type DashboardExposureMeasure } from '@/features/dashboard/filters'
import { formatCurrency, formatCurrencyAxis, formatDate } from '@/lib/format'
import type { ExposureMeasure } from '@/types/analytics'

type CurrencyExposureData = {
  currency?: string
  measure: ExposureMeasure
  measure_label: string
  series: Array<{ key: string; label: string; kind: string }>
  points: Array<{ period_start: string; period_end: string; [key: string]: string | number | null }>
}

type Props = {
  data?: CurrencyExposureData
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
  measure: DashboardExposureMeasure
  onMeasureChange: (measure: DashboardExposureMeasure) => void
}

const MEASURE_LABELS: Record<DashboardExposureMeasure, string> = {
  property_value: 'Property value', debt: 'Debt', rental_income: 'Rental income',
}

function exposureState({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load currency exposure.', onRetry }
  if (!data || data.points.length === 0 || data.series.length === 0) return { status: 'empty', message: 'No currency exposure data for this selection.' }
  return { status: 'success' }
}

export function CurrencyExposureChart(props: Props) {
  const { data, measure, onMeasureChange } = props
  const state = exposureState(props)
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const series = data?.series.map((item, index) => ({ ...item, visualToken: (['primary', 'secondary', 'tertiary'] as const)[index % 3] })) ?? []
  const visibleKeys = new Set(series.filter((item) => !hiddenKeys.has(item.key)).map((item) => item.key))
  const rows = data ? data.points.flatMap((point) => series.filter((item) => visibleKeys.has(item.key)).map((item) => ({
    id: `${point.period_start}-${item.key}`,
    period: point.period_start,
    currency: item.label,
    value: point[item.key] as number | null,
    visualToken: item.visualToken,
  }))) : []
  const table = data ? {
    columns: [{ key: 'period', label: 'Period' }, { key: 'currency', label: 'Currency' }, { key: 'value', label: data.measure_label, numeric: true }],
    rows: rows.map((row) => ({ period: formatDate(row.period), currency: row.currency, value: formatCurrency(row.value, data.currency ?? '') })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Currency exposure"
      subtitle={data ? `${data.measure_label} grouped by native currency, as supplied by the exposure endpoint.` : 'Exposure supplied by the exposure endpoint.'}
      controls={<><label className="sr-only" htmlFor="exposure-measure">Exposure measure</label><select id="exposure-measure" aria-label="Exposure measure" className="min-h-11 rounded-md border bg-background px-3 text-sm focus-visible:ring-3" value={measure} onChange={(event) => onMeasureChange(event.target.value as DashboardExposureMeasure)}>{EXPOSURE_MEASURES.map((option) => <option key={option} value={option}>{MEASURE_LABELS[option]}</option>)}</select>{state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => { const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next })} />}</>}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 12, left: 72, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis type="number" tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} />
              <YAxis type="category" dataKey="currency" width={68} tick={{ fontSize: 12 }} />
              <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={String(label)} rows={(payload ?? []).map((item) => ({ label: data.measure_label, value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
              <Bar dataKey="value" name={data.measure_label}>{rows.map((row) => <Cell key={row.id} fill={chartSeriesStyle(row.visualToken).color} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
          <ul className="sr-only" aria-label="Currency exposure values">{rows.map((row) => <li key={row.id} data-testid={`currency-exposure-bar-${row.id}`}>{formatDate(row.period)} {row.currency}: {formatCurrency(row.value, data.currency ?? '')}</li>)}</ul>
        </>
      )}
    </AnalyticsChartCard>
  )
}
