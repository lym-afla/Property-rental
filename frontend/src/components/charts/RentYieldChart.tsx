// frontend/src/components/charts/RentYieldChart.tsx
//
// Rent Yield line chart (Plan C Task 8). Shows rent yield per period,
// defined as rent received in the period divided by the property's
// current notional value, expressed as a percentage.
//
// The chart-data endpoint for a property carries a `rent` series; the
// property's value is taken from the latest PropertyValuation (or, if
// no valuation exists, falls back to 1 so the chart still renders
// without divide-by-zero noise). Yield % = rent / value × 100.
import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { usePropertyValuations } from '@/api/propertyValuations'
import type { ChartDataResponse } from '@/api/charts'

type Props = {
  data: ChartDataResponse
  propertyId: number
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return `${value.toFixed(1)}%`
}

export function RentYieldChart({ data, propertyId }: Props) {
  const { chartData, series } = transformForRecharts(data)
  const valuations = usePropertyValuations(propertyId)

  // Latest valuation = highest capital_structure_date. Fall back to 1 so
  // we never divide by zero; if there are zero valuations the chart
  // simply renders a flat yield of rent / 1, which is still meaningful
  // as a "rent received" trend.
  const value = useMemo(() => {
    const list = valuations.data ?? []
    if (list.length === 0) return 1
    const latest = [...list].sort((a, b) =>
      a.capital_structure_date < b.capital_structure_date ? 1 : -1,
    )[0]
    const parsed = Number(latest?.capital_structure_value)
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1
  }, [valuations.data])

  // Sum of all series per period is interpreted as "rent received" for
  // that period (the chart-data request for a property typically returns
  // only the rent category, but we sum defensively so any extra series
  // doesn't break the chart).
  const yieldData = chartData.map(row => {
    const rent = series.reduce((acc, s) => acc + (Number(row[s.key]) || 0), 0)
    return {
      label: row.label,
      yield: value > 0 ? (rent / value) * 100 : 0,
    }
  })

  const tableData = {
    headers: ['Period', 'Yield %'],
    rows: yieldData.map(row => [row.label as string, Number(row.yield.toFixed(2))]),
  }

  if (valuations.isLoading) {
    return (
      <ChartCard title="Rent yield" description={`Rent / value per period (value: 1)`}>
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Rent yield"
      description={`Rent / value per period (value: ${value.toLocaleString()})`}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={yieldData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatPercent(Number(v))} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => formatPercent(Number(v))} />
          <Line
            type="monotone"
            dataKey="yield"
            name="Rent yield"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
