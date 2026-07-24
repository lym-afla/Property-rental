// frontend/src/components/charts/CurrencyExposureChart.tsx
//
// Horizontal bar chart showing portfolio GROSS INCOME (revenue) exposure
// grouped by currency.
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
// Timeline: a YTD / All selector switches between `gross_income_ytd` and
// `gross_income_all_time`. `with_stats` only computes these two windows
// (it does NOT support arbitrary "last N months" ranges), so we expose
// exactly the two periods that have correct totals rather than a wider
// selector that silently returned the wrong number. The user wants GROSS
// INCOME (revenue), not net income — that is `gross_income_*`, the same
// figure the Properties page shows.
import { useMemo, useState } from 'react'
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

type ExposureRow = {
  currency: string    // native currency (RUB/GBP) — Y axis label + table key
  nativeValue: number // sum of native-currency gross income across properties
  usdValue: number    // same sum, FX-converted to user currency (the chart value)
}

// Timeline options that map 1:1 to fields `with_stats` actually computes.
// `YTD` -> `gross_income_ytd`; `All` -> `gross_income_all_time`. We
// deliberately do NOT expose 3m / 6m / 12m / 3Y / 5Y here because
// `with_stats` would silently fall back to all-time totals for those
// windows, which is misleading. When/if the backend starts supporting
// arbitrary date ranges, this list can grow.
const TIMELINE_OPTIONS = [
  { value: 'YTD', label: 'Year to date' },
  { value: 'All', label: 'All time' },
] as const

type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

type Props = {
  // Optional controlled timeline + setter. When omitted the chart manages
  // its own state so it can drop into pages that don't care about the
  // selector (and keep working as before). The dashboard does NOT pass
  // these — the chart owns its own selector in the card header.
  timeline?: Timeline
  onTimelineChange?: (t: Timeline) => void
}

export function CurrencyExposureChart({ timeline, onTimelineChange }: Props) {
  // The user's preferred display currency drives the FX-converted totals
  // (the bar values). Falls back to USD when the session has not loaded
  // yet or the user never picked a currency.
  const { user } = useSession()
  const userCurrency = user?.default_currency || 'USD'

  // Default to All-time gross income (matches the previous chart's
  // "all-time net income" default window but now uses gross income).
  const [internalTimeline, setInternalTimeline] = useState<Timeline>('All')
  const selectedTimeline = timeline ?? internalTimeline
  const handleTimelineChange = onTimelineChange ?? setInternalTimeline

  // Two parallel snapshots: user-currency-converted (for the chart axis)
  // and native (for the table's "face value" column). React Query dedupes
  // them by query key. `asOf` is intentionally omitted — `with_stats`
  // defaults to today, which (as the upper bound of the all-time window)
  // includes every transaction.
  const usdStats = usePropertiesWithStats(undefined, userCurrency)
  const nativeStats = usePropertiesWithStats(undefined, 'native')

  // Pick the gross income field that matches the selected window. We use
  // GROSS INCOME (revenue) — not net income — so the chart lines up with
  // the per-property gross figures the Properties page shows.
  const grossField: 'gross_income_ytd' | 'gross_income_all_time' =
    selectedTimeline === 'YTD' ? 'gross_income_ytd' : 'gross_income_all_time'
  const periodLabel = selectedTimeline === 'YTD' ? 'Year to date' : 'All time'

  const chartData = useMemo(() => {
    const byCurrency = new Map<string, ExposureRow>()
    // USD-converted values drive the bar lengths; group properties by
    // their NATIVE currency so the Y axis still labels the exposure the
    // user cares about.
    for (const p of usdStats.data ?? []) {
      const cur = p.currency || '???'
      const usdValue = Math.abs(p[grossField] ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.usdValue += usdValue
      else byCurrency.set(cur, { currency: cur, nativeValue: 0, usdValue })
    }
    // Native-currency totals fill the table's "face value" column.
    for (const p of nativeStats.data ?? []) {
      const cur = p.currency || '???'
      const nativeValue = Math.abs(p[grossField] ?? 0)
      const existing = byCurrency.get(cur)
      if (existing) existing.nativeValue += nativeValue
      else byCurrency.set(cur, { currency: cur, nativeValue, usdValue: 0 })
    }
    return Array.from(byCurrency.values()).sort((a, b) => b.usdValue - a.usdValue)
  }, [usdStats.data, nativeStats.data, grossField])

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

  const controls = (
    <Select
      value={selectedTimeline}
      onValueChange={(v) => handleTimelineChange(v as Timeline)}
    >
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
        title="Gross income by currency"
        description={`${periodLabel} gross income (${userCurrency}-converted)`}
        controls={controls}
        tableData={tableData}
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
        title="Gross income by currency"
        description={`${periodLabel} gross income (${userCurrency}-converted)`}
        controls={controls}
        tableData={tableData}
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          No data
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Gross income by currency"
      description={`${periodLabel} gross income (${userCurrency}-converted)`}
      controls={controls}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 5, right: 20, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis type="number" tickFormatter={(v) => formatCurrencyAxis(v, userCurrency)} tick={{ fontSize: 12 }} />
          <YAxis type="category" dataKey="currency" tick={{ fontSize: 12 }} width={50} />
          <Tooltip formatter={(v) => formatCurrency(Number(v), userCurrency)} />
          <Bar dataKey="usdValue" name={`Gross income (${userCurrency})`}>
            {chartData.map((entry, i) => (
              <Cell key={`cell-${i}`} fill={colorForCategory(entry.currency, i)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
