// frontend/src/components/charts/ValuationChart.tsx
//
// Property Valuation combo chart (Plan C Task 8). Stacked bar (Debt +
// Equity) plus a Line overlay showing total property value over time.
//
// The chart-data endpoint for a property returns Debt + Equity series
// (see `ChartDataView`); transformForRecharts maps those onto rows. The
// "total" trajectory line is just the per-period sum of those two — i.e.
// the property value itself — drawn as a Line overlay so users can see
// the bar composition *and* the value trend in a single panel.
//
// Click a bar to drill into /transactions?... for that period.
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrencyAxis } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
  onBarClick?: (period: string) => void
}

export function ValuationChart({ data, onBarClick }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)

  // Augment each row with a synthetic `value` field = Debt + Equity (or
  // whichever series the backend happened to send). ComposedChart can
  // then render the same row both as stacked bars and as a line.
  const enrichedData: Record<string, number | string>[] = chartData.map(row => {
    const total = series.reduce((acc, s) => acc + (Number(row[s.key]) || 0), 0)
    return { ...row, value: total }
  })

  const tableData = {
    headers: ['Period', ...series.map(s => s.label), 'Value'],
    rows: enrichedData.map(row => [
      row.label as string,
      ...series.map(s => row[s.key] as number),
      row.value as number,
    ]),
  }

  return (
    <ChartCard
      title="Valuation"
      description="Debt + Equity stacked, total value overlay"
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={enrichedData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
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
              stackId="valuation"
              fill={s.color}
              onClick={(payload: any) => onBarClick?.(payload.label)}
              cursor={onBarClick ? 'pointer' : 'default'}
            />
          ))}
          <Line
            type="monotone"
            dataKey="value"
            name="Total value"
            stroke="#0f172a"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
