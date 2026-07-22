// frontend/src/components/charts/ExpenseBreakdownChart.tsx
//
// Donut chart showing expense proportions by category.
// Filters to expense categories only (negative values in chart data),
// showing absolute values for the donut.
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import type { ReactNode } from 'react'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrency } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

// Known income categories — exclude from expense breakdown
const INCOME_CATEGORIES = ['rent', 'other_income', 'capax', 'capex']

type Props = {
  data: ChartDataResponse
  // Optional controls rendered in the card header (e.g. a timeline Select).
  controls?: ReactNode
}

export function ExpenseBreakdownChart({ data, controls }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)

  // One slice per EXPENSE series (negative values), summed across periods.
  // Income categories (rent, other_income) are excluded.
  const pieData = series
    .filter(s => !INCOME_CATEGORIES.includes(s.key.toLowerCase()))
    .map(s => {
      const total = chartData.reduce((acc, row) => acc + Math.abs(Number(row[s.key]) || 0), 0)
      return { name: s.label, value: total, color: s.color }
    })
    .filter(d => d.value > 0)

  // Table + tooltip use the full `#,###` form (`formatCurrency`); the `k`
  // compact form is reserved for chart axes only.
  const tableData = {
    headers: ['Expense Category', 'Total'],
    rows: pieData.map(d => [d.name, formatCurrency(d.value, currency)]),
  }

  return (
    <ChartCard title="Expense breakdown" description={`Spend by category (${currency})`} controls={controls} tableData={tableData}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Tooltip formatter={(v) => formatCurrency(Number(v), currency)} />
          <Legend />
          <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={100} paddingAngle={2}>
            {pieData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={entry.color} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
