// frontend/src/components/charts/ExpenseBreakdownChart.tsx
//
// Donut chart (Plan C Task 5) showing expense proportions by category for
// the supplied window. Consumes the same ChartDataResponse shape as the
// other charts (so a "last 12 months" chart-data request can power it
// directly), aggregates every series total, and renders with Recharts
// PieChart + innerRadius. The Legend is interactive — click a slice to
// toggle visibility (handled by Recharts out of the box).
import {
  PieChart,
  Pie,
  Cell,
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
}

export function ExpenseBreakdownChart({ data }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)

  // One slice per series, summed across every period. Categories with no
  // spend in the window are dropped so the donut stays readable.
  const pieData = series
    .map(s => ({
      name: s.label,
      value: chartData.reduce((acc, row) => acc + (Number(row[s.key]) || 0), 0),
      color: s.color,
    }))
    .filter(d => d.value > 0)

  const tableData = {
    headers: ['Category', 'Total'],
    rows: pieData.map(d => [d.name, d.value]),
  }

  return (
    <ChartCard
      title="Expense breakdown"
      description="Spend by category"
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Tooltip formatter={(v) => formatCurrencyAxis(Number(v), currency)} />
          <Legend />
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={2}
          >
            {pieData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
