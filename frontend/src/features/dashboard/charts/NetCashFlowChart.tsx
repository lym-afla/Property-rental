import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import { cashTable, chartState, compactPeriod, hasSeriesValues, seriesWithVisualTokens, type ChartDataProps, type DrillDown, type PortfolioChartData } from './chartUtils'

type Props = ChartDataProps & {
  propertyIds?: readonly number[]
  onDrillDown?: (drillDown: DrillDown) => void
}

const CASH_FLOW_CATEGORY_KINDS = new Set(['income_category', 'expense_category'])

function categorySeries(data: PortfolioChartData) {
  return data.series.filter((item) => CASH_FLOW_CATEGORY_KINDS.has(item.kind))
}

export function NetCashFlowChart({ data, isLoading, isError, onRetry, propertyIds = [], onDrillDown }: Props) {
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const series = data ? seriesWithVisualTokens(categorySeries(data)) : []
  const state = chartState('Net cash flow', { data, isLoading, isError, onRetry }, hasSeriesValues(data, series))
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const drill = (point: PortfolioChartData['points'][number], category: string) => onDrillDown?.({
    from: point.period_start, to: point.period_end, category, currency: data?.currency ?? '', propertyIds,
  })

  return (
    <AnalyticsChartCard
      state={state}
      title="Net cash flow"
      subtitle="Signed income and expense categories by reporting period."
      controls={state.status === 'success' && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next
      })} />}
      table={state.status === 'success' && data ? cashTable(data, series) : undefined}
    >
      {state.status === 'success' && data && <div className="flex h-full min-h-0 flex-col">
        <span className="sr-only" aria-label="Net cash flow zero baseline">Zero baseline shown on the chart.</span>
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.points} stackOffset="sign" margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="period_start" tickFormatter={compactPeriod} minTickGap={24} />
            <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} />
            <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={compactPeriod(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(typeof item.value === 'number' ? item.value : null, data.currency ?? '') }))} /> : null} />
            <ReferenceLine y={0} stroke="currentColor" aria-label="Net cash flow zero baseline" />
            {visibleSeries.map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} stackId="cash-flow" fill={chartSeriesStyle(item.visualToken).color} stroke={chartSeriesStyle(item.visualToken).color} onClick={(entry) => drill(entry as unknown as PortfolioChartData['points'][number], item.key)} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <details className="mt-2 rounded-md border px-2 py-1">
          <summary className="min-h-11 cursor-pointer content-center font-medium">Drill down to transactions</summary>
          <div className="grid max-h-28 grid-cols-1 gap-1 overflow-y-auto pb-1 sm:grid-cols-2">
            {data.points.flatMap((point) => series.map((item) => <button className="min-h-11 rounded-md border px-2 text-left text-sm hover:bg-muted focus-visible:ring-3" key={`${point.period_start}-${item.key}`} type="button" onClick={() => drill(point, item.key)}>View {item.label} transactions for {compactPeriod(point.period_start)}</button>))}
          </div>
        </details>
      </div>}
    </AnalyticsChartCard>
  )
}
