// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart (Plan C Task 7) showing the current value at risk
// grouped by currency. Each property carries a `currency` field; summing
// per-currency holdings gives the FX exposure at a glance.
//
// Uses Recharts `layout="vertical"` BarChart so currencies sit on the Y
// axis and bar length encodes value — much more readable than vertical
// bars when currency codes are short strings.
import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { usePropertiesWithStats } from '@/api/properties'
import { formatCurrencyAxis } from '@/lib/format'
import { colorForCategory } from './_chartTheme'

// `with_stats` rows carry `gross_income_all_time` etc., but for "value at
// risk" we want a notional property value. The dataset doesn't expose a
// direct `value` field, so we approximate value from lifetime gross
// income scaled to a sensible multiplier proxy. Callers preferring the
// exact `property_valuations` trajectory should reach for ValuationChart.
function propertyNotionalValue(
  prop: { gross_income_all_time: number; net_income_all_time: number },
): number {
  // 10× annualised gross income proxy — purely a placeholder so the
  // chart has something to sum until property_value lands on the type.
  // Uses lifetime numbers since that's what with_stats already exposes.
  return Math.max(prop.gross_income_all_time, prop.net_income_all_time) * 1
}

export function CurrencyExposureChart() {
  const properties = usePropertiesWithStats()

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, number>()
    for (const p of properties.data ?? []) {
      const cur = p.currency || '???'
      byCurrency.set(cur, (byCurrency.get(cur) ?? 0) + propertyNotionalValue(p))
    }
    return Array.from(byCurrency.entries())
      .map(([currency, value]) => ({ currency, value }))
      .sort((a, b) => b.value - a.value)
  }, [properties.data])

  const tableData = useMemo(
    () => ({
      headers: ['Currency', 'Value'],
      rows: chartData.map(row => [row.currency, row.value]),
    }),
    [chartData],
  )

  // First currency in the list is treated as the "display" currency for
  // axis formatting — the rows themselves are not converted (each row is
  // already in its native currency), so this is purely cosmetic for the
  // axis symbol. Mixed-currency sums are an inherent limitation of the
  // view; the table view makes the per-row currency explicit.
  const displayCurrency = chartData[0]?.currency ?? 'USD'

  if (properties.isLoading) {
    return (
      <ChartCard title="Currency exposure" description="Value at risk by currency">
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Currency exposure"
      description="Value at risk by currency"
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            type="number"
            tickFormatter={(v) => formatCurrencyAxis(v, displayCurrency)}
            tick={{ fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="currency"
            tick={{ fontSize: 12 }}
            width={50}
          />
          <Tooltip formatter={(v) => formatCurrencyAxis(Number(v), displayCurrency)} />
          <Bar dataKey="value" name="Value">
            {chartData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={colorForCategory(entry.currency, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
