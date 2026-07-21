// frontend/src/components/charts/CashFlowChart.tsx
//
// Headline dashboard chart (Plan C Task 3). Diverging stacked bar — each
// period is one bar, split by series (income categories above, expense
// categories below via sign on the underlying data). Click a bar segment
// to drill into /transactions?... for that period + category, and the
// Recharts Brush gives time-range scrubbing for long histories.
//
// All shape translation lives in `transformForRecharts`; this component
// is purely presentation.
import type { ReactNode } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, Brush, ResponsiveContainer } from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrencyAxis } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
  onBarClick?: (period: string, category: string) => void
  // Forwarded to ChartCard so the dashboard can render the frequency +
  // timeline selectors in the chart header (next to the "Table" toggle).
  controls?: ReactNode
}

export function CashFlowChart({ data, onBarClick, controls }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)
  const tableData = {
    headers: ['Period', ...series.map(s => s.label)],
    rows: chartData.map(row => [row.label as string, ...series.map(s => row[s.key] as number)]),
  }
  return (
    <ChartCard title="Cash Flow" description="Income vs expenses by period" controls={controls} tableData={tableData}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, currency)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => formatCurrencyAxis(Number(v), currency)} />
          <Legend />
          {series.map(s => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              stackId="a"
              onClick={(payload: any) => onBarClick?.(payload.label, s.key)}
              cursor={onBarClick ? 'pointer' : 'default'}
            />
          ))}
          <Brush dataKey="label" height={20} stroke="#3b82f6" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
