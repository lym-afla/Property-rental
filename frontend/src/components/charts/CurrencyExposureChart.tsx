// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart showing portfolio exposure grouped by currency.
// Uses lifetime net income per property (from with_stats) as the value proxy,
// grouped by each property's native currency.
//
// IMPORTANT: the stats values returned by `with_stats` are FX-converted into
// a single target currency (almost always USD, exposed as `stats_currency`).
// The chart's grouping key is the property's NATIVE `currency` (RUB/GBP/etc.),
// but the BAR VALUES are denominated in `stats_currency`. We therefore:
//   - group/sort by `p.currency` (native) for the Y axis labels
//   - format the values with `p.stats_currency` (USD) so the symbol matches
//     the underlying amounts
//
// Task: an "as of" Select lets the user pick the snapshot date — Current
// (today), 1Y ago, 3Y ago, or All time (1900-01-01 sentinel). The choice is
// forwarded to `usePropertiesWithStats` as the `asOf` query param so the
// backend recomputes the aggregates through that date.
import { useMemo, useState, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { usePropertiesWithStats } from '@/api/properties'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import { colorForCategory } from './_chartTheme'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type ExposureRow = {
  currency: string         // native currency (RUB/GBP) — Y axis label
  statsCurrency: string    // currency the value is denominated in (USD)
  value: number
}

// "As of" options for the snapshot date. The values are ISO dates computed
// once at module load; All time uses the backend's `1900-01-01` sentinel
// (the chart-data service rewrites it to the property set's earliest
// transaction date, and with_stats interprets it the same way for the
// end-date window — effectively "include everything").
const AS_OF_OPTIONS = [
  { value: 'current', label: 'Current' },
  { value: '1Y', label: '1 year ago' },
  { value: '3Y', label: '3 years ago' },
  { value: 'All', label: 'All time' },
] as const

type AsOf = (typeof AS_OF_OPTIONS)[number]['value']

function asOfToIso(asOf: AsOf): string | undefined {
  const today = new Date()
  if (asOf === 'current') return undefined // omit param; backend defaults to today
  if (asOf === 'All') return '1900-01-01'
  const d = new Date(today)
  if (asOf === '1Y') d.setFullYear(d.getFullYear() - 1)
  else if (asOf === '3Y') d.setFullYear(d.getFullYear() - 3)
  return d.toISOString().slice(0, 10)
}

export function CurrencyExposureChart() {
  const [asOf, setAsOf] = useState<AsOf>('current')
  const asOfIso = useMemo(() => asOfToIso(asOf), [asOf])
  const properties = usePropertiesWithStats(asOfIso)

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, ExposureRow>()
    for (const p of properties.data ?? []) {
      const cur = p.currency || '???'
      // Stats are FX-converted to USD on the backend; preserve that fact so
      // the value formatting uses the right symbol below.
      const statsCurrency = p.stats_currency ?? 'USD'
      // Use lifetime net income as the value proxy.
      const value = Math.abs(p.net_income_all_time ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) {
        existing.value += value
      } else {
        byCurrency.set(cur, { currency: cur, statsCurrency, value })
      }
    }
    return Array.from(byCurrency.values()).sort((a, b) => b.value - a.value)
  }, [properties.data])

  // All properties share the same stats currency (USD), so the axis
  // formatter uses the first row's statsCurrency — falling back to USD if
  // there's no data.
  const axisCurrency = chartData[0]?.statsCurrency ?? 'USD'

  const tableData = useMemo(
    () => ({
      headers: ['Currency', `Net income (${axisCurrency})`],
      rows: chartData.map(row => [
        row.currency,
        formatCurrency(row.value, row.statsCurrency),
      ]),
    }),
    [chartData, axisCurrency],
  )

  const controls: ReactNode = (
    <Select value={asOf} onValueChange={(v) => setAsOf(v as AsOf)}>
      <SelectTrigger className="h-8 w-[150px]" aria-label="Currency exposure as of">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {AS_OF_OPTIONS.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  if (properties.isLoading) {
    return (
      <ChartCard
        title="Currency exposure"
        description="Net income by currency"
        controls={controls}
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  if (chartData.length === 0) {
    return (
      <ChartCard
        title="Currency exposure"
        description="Net income by currency"
        controls={controls}
      >
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
      controls={controls}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(v) => formatCurrencyAxis(v, axisCurrency)} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="currency" tick={{ fontSize: 12 }} width={50} />
          <Tooltip formatter={(v, _name, item) => {
            const num = Number(v)
            const row = (item?.payload as ExposureRow | undefined) ?? chartData.find(d => d.value === num)
            const cur = row?.statsCurrency ?? axisCurrency
            return formatCurrency(num, cur)
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
