// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart showing portfolio exposure grouped by currency.
// Uses lifetime net income per property (from with_stats) as the value proxy,
// grouped by each property's native currency.
import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { usePropertiesWithStats } from '@/api/properties'
import { formatCurrencyAxis } from '@/lib/format'
import { colorForCategory } from './_chartTheme'

export function CurrencyExposureChart() {
  const properties = usePropertiesWithStats()

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, number>()
    for (const p of properties.data ?? []) {
      const cur = p.currency || '???'
      // Use lifetime net income as the value proxy
      const value = Math.abs(p.net_income_all_time ?? 0)
      byCurrency.set(cur, (byCurrency.get(cur) ?? 0) + value)
    }
    return Array.from(byCurrency.entries())
      .map(([currency, value]) => ({ currency, value }))
      .sort((a, b) => b.value - a.value)
  }, [properties.data])

  const tableData = useMemo(
    () => ({
      headers: ['Currency', 'Net Income (native)'],
      rows: chartData.map(row => [row.currency, formatCurrencyAxis(row.value, row.currency)]),
    }),
    [chartData],
  )

  if (properties.isLoading) {
    return (
      <ChartCard title="Currency exposure" description="Net income by currency">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartCard title="Currency exposure" description="Net income by currency">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          No data
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Currency exposure"
      description="Net income by currency"
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(v) => formatCurrencyAxis(v, 'USD')} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="currency" tick={{ fontSize: 12 }} width={50} />
          <Tooltip formatter={(v) => {
            const num = Number(v)
            const cur = chartData.find(d => d.value === num)?.currency ?? 'USD'
            return formatCurrencyAxis(num, cur)
          }} />
          <Bar dataKey="value" name="Net income">
            {chartData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={colorForCategory(entry.currency, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
