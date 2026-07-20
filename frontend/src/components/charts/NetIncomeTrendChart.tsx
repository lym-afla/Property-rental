// frontend/src/components/charts/NetIncomeTrendChart.tsx
//
// Companion to CashFlowChart (Plan C Task 4). Net income trajectory per
// period, derived client-side as the sum of every series in the chart
// data — that way a single component works whether the backend returns
// income-only, expense-only, or both, and "net" means literally the sum
// of every datapoint for the period.
//
// Rendered as an AreaChart with a vertical gradient so the trend is
// visually distinct from the CashFlow bar chart on the same page. A
// Recharts Brush mirrors the CashFlow scrubbing affordance.
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Brush,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrencyAxis } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
}

export function NetIncomeTrendChart({ data }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)

  // Net = sum of every numeric series value for the period. Label is
  // preserved as-is for the X axis.
  const netData = chartData.map(row => ({
    label: row.label,
    net: series.reduce((acc, s) => acc + (Number(row[s.key]) || 0), 0),
  }))

  const tableData = {
    headers: ['Period', 'Net income'],
    rows: netData.map(row => [row.label as string, row.net]),
  }

  return (
    <ChartCard title="Net income trend" description="Net income by period" tableData={tableData}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={netData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="netIncomeGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, currency)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => formatCurrencyAxis(Number(v), currency)} />
          <Area
            type="monotone"
            dataKey="net"
            name="Net income"
            stroke="#10b981"
            strokeWidth={2}
            fill="url(#netIncomeGradient)"
          />
          <Brush dataKey="label" height={20} stroke="#10b981" />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
