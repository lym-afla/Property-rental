import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { AnalyticsChartCard, type AnalyticsChartState } from '@/components/analytics/AnalyticsChartCard'
import { ResponsiveChartContainer } from '@/components/analytics/ResponsiveChartContainer'
import { ChartTooltip } from '@/components/analytics/ChartTooltip'
import { chartVisualTokens } from '@/components/analytics/chartTheme'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import type { PropertyContributionResponse } from '@/types/analytics'

type Props = {
  data?: PropertyContributionResponse
  isLoading?: boolean
  isError?: boolean
  onRetry?: () => void
}

function contributionState({ data, isLoading, isError, onRetry }: Props): AnalyticsChartState {
  if (isLoading) return { status: 'loading' }
  if (isError) return { status: 'error', message: 'Could not load property contribution.', onRetry }
  if (!data || data.rows.length === 0) return { status: 'empty', message: 'No property contribution data for this selection.' }
  return { status: 'success' }
}

export function PropertyContributionChart(props: Props) {
  const { data } = props
  const state = contributionState(props)
  const rows = data ? [...data.rows].sort((left, right) => right.net_income - left.net_income) : []
  const table = data ? {
    columns: [
      { key: 'property', label: 'Property' },
      { key: 'netIncome', label: 'Net income', numeric: true },
      { key: 'share', label: 'Portfolio share', numeric: true },
      { key: 'direction', label: 'Direction' },
    ],
    rows: rows.map((row) => ({
      property: row.property_name,
      netIncome: formatCurrency(row.net_income, data.currency),
      share: row.portfolio_share === null ? '—' : `${row.portfolio_share.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`,
      direction: row.net_income < 0 ? 'Negative contributor' : 'Positive contributor',
    })),
  } : undefined

  return (
    <AnalyticsChartCard
      state={state}
      title="Property contribution"
      subtitle="Signed selected-period net income supplied for each property."
      summary={state.status === 'success' && <p className="text-sm text-muted-foreground">Positive and negative contributors are labelled in the exact-value table.</p>}
      table={state.status === 'success' ? table : undefined}
    >
      {state.status === 'success' && data && (
        <>
          <ResponsiveChartContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 12, left: 36, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis type="number" tickFormatter={(value) => formatCurrencyAxis(Number(value), data.currency)} />
              <YAxis type="category" dataKey="property_name" width={132} tick={{ fontSize: 12 }} />
              <ReferenceLine x={0} stroke="currentColor" />
              <Tooltip content={({ active, label, payload }) => active ? <ChartTooltip label={String(label)} rows={(payload ?? []).map((item) => ({ label: 'Net income', value: formatCurrency(Number(item.value), data.currency) }))} /> : null} />
              <Bar dataKey="net_income" name="Net income">
                {rows.map((row) => <Cell key={row.property_id} fill={row.net_income < 0 ? chartVisualTokens.tertiary.color : chartVisualTokens.primary.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveChartContainer>
          <ul className="sr-only" aria-label="Property contribution values">
            {rows.map((row) => <li key={row.property_id} data-testid={`property-contribution-${row.property_id}`} data-net-income={row.net_income}>{row.property_name}: {formatCurrency(row.net_income, data.currency)} — {row.net_income < 0 ? 'Negative contributor' : 'Positive contributor'}</li>)}
          </ul>
          {rows.some((row) => row.net_income < 0) && <p className="sr-only">Negative contributor</p>}
        </>
      )}
    </AnalyticsChartCard>
  )
}
