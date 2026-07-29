import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard } from '@/components/analytics/AnalyticsChartCard'
import { ChartLegend } from '@/components/analytics/ChartLegend'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartSeriesStyle } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import { cashTable, chartState, compactPeriod, seriesWithVisualTokens, type ChartDataProps, type DrillDown, type PortfolioChartData } from './chartUtils'

type Props = ChartDataProps & {
  propertyIds?: readonly number[]
  onDrillDown?: (drillDown: DrillDown) => void
}

const AGGREGATE_KEYS = new Set(['total_income', 'total_expenses', 'net_income', 'cumulative_net_income'])

function categorySeries(data: PortfolioChartData) {
  return data.series.filter((item) => !AGGREGATE_KEYS.has(item.key))
}

export function NetCashFlowChart({ data, isLoading, isError, onRetry, propertyIds = [], onDrillDown }: Props) {
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set())
  const state = chartState('Net cash flow', { data, isLoading, isError, onRetry })
  const series = data ? seriesWithVisualTokens(categorySeries(data)) : []
  const visibleSeries = series.filter((item) => !hiddenKeys.has(item.key))
  const drill = (point: PortfolioChartData['points'][number], category: string) => onDrillDown?.({
    from: point.period_start, to: point.period_end, category, currency: data?.currency ?? '', propertyIds,
  })

  return (
    <AnalyticsChartCard
      state={state}
      title="Net cash flow"
      subtitle="Signed income and expense categories by reporting period."
      controls={data && <ChartLegend series={series} hiddenKeys={hiddenKeys} onToggle={(key) => setHiddenKeys((current) => {
        const next = new Set(current); next.has(key) ? next.delete(key) : next.add(key); return next
      })} />}
      table={data ? cashTable(data, series) : undefined}
    >
      {data && <>
        <span className="sr-only" aria-label="Net cash flow zero baseline">Zero baseline shown on the chart.</span>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data.points} margin={{ top: 16, right: 12, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="period_start" tickFormatter={compactPeriod} minTickGap={24} />
            <YAxis tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency ?? '')} />
            <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={compactPeriod(String(label))} rows={(payload ?? []).map((item) => ({ label: String(item.name), value: formatCurrency(Number(item.value), data.currency ?? '') }))} /> : null} />
            <ReferenceLine y={0} stroke="currentColor" aria-label="Net cash flow zero baseline" />
            {visibleSeries.map((item) => <Bar key={item.key} dataKey={item.key} name={item.label} stackId="cash-flow" fill={chartSeriesStyle(item.visualToken).color} onClick={(entry) => drill(entry as unknown as PortfolioChartData['points'][number], item.key)} />)}
          </BarChart>
        </ResponsiveContainer>
        <div className="sr-only" aria-label="Net cash flow drill-down controls">
          {data.points.flatMap((point) => series.map((item) => <button key={`${point.period_start}-${item.key}`} type="button" onClick={() => drill(point, item.key)}>View {item.label} transactions for {compactPeriod(point.period_start)}</button>))}
        </div>
      </>}
    </AnalyticsChartCard>
  )
}
