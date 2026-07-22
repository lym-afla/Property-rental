// frontend/src/components/charts/TenantRentChart.tsx
//
// Tenant rent history bar chart (Plan C Task 9). Single-series BarChart
// of rent received per period for one tenant, with a Brush for long
// tenancies. Data comes from `useChartData({ type: 'tenant', elementId })`.
//
// Click a bar to drill into /transactions?tenant=...&period=... for the
// underlying transactions in that period.
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Brush,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
  onBarClick?: (period: string) => void
}

export function TenantRentChart({ data, onBarClick }: Props) {
  const { chartData, series, currency } = transformForRecharts(data)

  // The chart-data endpoint returns one series for a tenant (rent), but
  // we render every series defensively so a future multi-series response
  // (e.g. rent vs. debt repayment) still works without changes.
  const tableData = {
    headers: ['Period', ...series.map(s => s.label)],
    rows: chartData.map(row => [row.label as string, ...series.map(s => row[s.key] as number)]),
  }

  return (
    <ChartCard
      title="Rent history"
      description="Rent received per period"
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          {/* Axis uses compact `k`; tooltip uses full `#,###` per spec. */}
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, currency)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => formatCurrency(Number(v), currency)} />
          {series.map(s => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              fill={s.color}
              onClick={(payload: any) => onBarClick?.(payload.label)}
              cursor={onBarClick ? 'pointer' : 'default'}
            />
          ))}
          <Brush dataKey="label" height={20} stroke="#3b82f6" />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
