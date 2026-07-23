// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart showing portfolio exposure grouped by currency.
//
// The chart fetches TWO `with_stats` snapshots:
//   - `currency=<userCurrency>` -> FX-converted totals so every bar sits
//                                  on a single-currency axis and is
//                                  directly comparable. `userCurrency` is
//                                  the user's `default_currency` (USD by
//                                  default).
//   - `currency='native'` -> each property's native-currency total so the
//                            table can show the face-value amount per
//                            currency group alongside the user-currency
//                            figure.
//
// Grouping key is the property's NATIVE `currency` (RUB/GBP/etc.) — that
// is what the user thinks of as "exposure to currency X". The BAR VALUES
// are FX-converted into the user's `default_currency`, so the chart is a
// single-currency comparison rather than a mix of ₽/£/$ amounts that
// can't be visually ranked.
//
// Timeline options match the rest of the dashboard (YTD / 3m / 6m /
// 12m / 3Y / 5Y / All). The choice is translated to an `as_of` ISO date
// and forwarded to `usePropertiesWithStats`; "All" uses `as_of=today`
// (the backend's all-time default — `as_of` is an upper bound, so today
// includes every transaction).
import { useMemo, useState, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { usePropertiesWithStats } from '@/api/properties'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import { useSession } from '@/context/SessionProvider'
import { colorForCategory } from './_chartTheme'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Timeline options — mirrors the dashboard's TIMELINE_OPTIONS so the
// currency-exposure selector reads identically to Cash Flow / Net
// Income Trend.
const TIMELINE_OPTIONS = [
  { value: 'YTD', label: 'Year to date' },
  { value: '3m', label: 'Last 3 months' },
  { value: '6m', label: 'Last 6 months' },
  { value: '12m', label: 'Last 12 months' },
  { value: '3Y', label: 'Last 3 years' },
  { value: '5Y', label: 'Last 5 years' },
  { value: 'All', label: 'All time' },
] as const

type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

// Translate a timeline selection into the `as_of` ISO date the
// `with_stats` endpoint expects. `as_of` is the upper bound of the
// all-time window; "All" therefore maps to today (the backend default),
// NOT to 1900-01-01 — passing a date in 1900 asked the backend to sum
// "through 1900", which produced zeros.
function timelineToAsOf(timeline: Timeline): string | undefined {
  const today = new Date()
  if (timeline === 'All') return undefined // backend defaults to today
  const d = new Date(today)
  switch (timeline) {
    case 'YTD':
      d.setMonth(0, 1) // Jan 1 of current year (covers YTD window)
      break
    case '3m':
      d.setMonth(d.getMonth() - 3)
      break
    case '6m':
      d.setMonth(d.getMonth() - 6)
      break
    case '12m':
      d.setFullYear(d.getFullYear() - 1)
      break
    case '3Y':
      d.setFullYear(d.getFullYear() - 3)
      break
    case '5Y':
      d.setFullYear(d.getFullYear() - 5)
      break
  }
  return d.toISOString().slice(0, 10)
}

type ExposureRow = {
  currency: string    // native currency (RUB/GBP) — Y axis label + table key
  nativeValue: number // sum of native-currency net income across properties
  usdValue: number    // same sum, FX-converted to user currency (the chart value)
}

export function CurrencyExposureChart() {
  const [timeline, setTimeline] = useState<Timeline>('All')
  const asOf = useMemo(() => timelineToAsOf(timeline), [timeline])
  // The user's preferred display currency drives the FX-converted totals
  // (the bar values). Falls back to USD when the session has not loaded
  // yet or the user never picked a currency.
  const { user } = useSession()
  const userCurrency = user?.default_currency || 'USD'

  // Two parallel snapshots: user-currency-converted (for the chart axis)
  // and native (for the table's "face value" column). React Query dedupes
  // them by query key, so flipping the timeline only re-fires the two
  // affected requests.
  const usdStats = usePropertiesWithStats(asOf, userCurrency)
  const nativeStats = usePropertiesWithStats(asOf, 'native')

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, ExposureRow>()
    // USD-converted values drive the bar lengths; group properties by
    // their NATIVE currency so the Y axis still labels the exposure the
    // user cares about.
    for (const p of usdStats.data ?? []) {
      const cur = p.currency || '???'
      const usdValue = Math.abs(p.net_income_all_time ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.usdValue += usdValue
      else byCurrency.set(cur, { currency: cur, nativeValue: 0, usdValue })
    }
    // Native-currency totals fill the table's "face value" column.
    for (const p of nativeStats.data ?? []) {
      const cur = p.currency || '???'
      const nativeValue = Math.abs(p.net_income_all_time ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.nativeValue += nativeValue
      else byCurrency.set(cur, { currency: cur, nativeValue, usdValue: 0 })
    }
    return Array.from(byCurrency.values()).sort((a, b) => b.usdValue - a.usdValue)
  }, [usdStats.data, nativeStats.data])

  const tableData = useMemo(
    () => ({
      // Two value columns: native-currency face value + user-currency.
      headers: ['Currency', 'Native', userCurrency],
      rows: chartData.map(row => [
        row.currency,
        formatCurrency(row.nativeValue, row.currency),
        formatCurrency(row.usdValue, userCurrency),
      ]),
    }),
    [chartData, userCurrency],
  )

  const controls: ReactNode = (
    <Select value={timeline} onValueChange={(v) => setTimeline(v as Timeline)}>
      <SelectTrigger className="h-8 w-[150px]" aria-label="Currency exposure timeline">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {TIMELINE_OPTIONS.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  if (usdStats.isLoading || nativeStats.isLoading) {
    return (
      <ChartCard
        title="Currency exposure"
        description={`Net income by currency (${userCurrency}-converted)`}
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
        description={`Net income by currency (${userCurrency}-converted)`}
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
      description={`Net income by currency (${userCurrency}-converted)`}
      controls={controls}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(v) => formatCurrencyAxis(v, userCurrency)} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="currency" tick={{ fontSize: 12 }} width={50} />
          <Tooltip formatter={(v) => formatCurrency(Number(v), userCurrency)} />
          <Bar dataKey="usdValue" name={`Net income (${userCurrency})`}>
            {chartData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={colorForCategory(entry.currency, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
