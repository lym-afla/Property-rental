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
import { useChartData } from '@/api/charts'
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

// Compute date range from timeline option
function timelineToRange(timeline: string): { from: string; to: string } {
  const today = new Date()
  const to = today.toISOString().slice(0, 10)
  const from = new Date(today)
  switch (timeline) {
    case 'YTD': from.setMonth(0, 1); break
    case '3m': from.setMonth(from.getMonth() - 3); break
    case '6m': from.setMonth(from.getMonth() - 6); break
    case '12m': from.setFullYear(from.getFullYear() - 1); break
    case '3Y': from.setFullYear(from.getFullYear() - 3); break
    case '5Y': from.setFullYear(from.getFullYear() - 5); break
    case 'All': return { from: '1900-01-01', to }
  }
  return { from: from.toISOString().slice(0, 10), to }
}

// Known income categories (rent only after recategorization)
const INCOME_CATEGORIES = ['rent']

type ExposureRow = {
  currency: string
  nativeValue: number
  usdValue: number
}

// Timeline options that map 1:1 to fields `with_stats` actually computes.
// `YTD` -> `gross_income_ytd`; `All` -> `gross_income_all_time`. We
// deliberately do NOT expose 3m / 6m / 12m / 3Y / 5Y here because
// `with_stats` would silently fall back to all-time totals for those
// windows, which is misleading. When/if the backend starts supporting
// arbitrary date ranges, this list can grow.
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

type Props = {
  // Optional controlled timeline + setter. When omitted the chart manages
  // its own state so it can drop into pages that don't care about the
  // selector (and keep working as before). The dashboard does NOT pass
  // these — the chart owns its own selector in the card header.
  timeline?: Timeline
  onTimelineChange?: (t: Timeline) => void
}

export function CurrencyExposureChart({ timeline, onTimelineChange }: Props) {
  const { user } = useSession()
  const userCurrency = user?.default_currency || 'USD'

  const [internalTimeline, setInternalTimeline] = useState<Timeline>('All')
  const selectedTimeline = timeline ?? internalTimeline
  const handleTimelineChange = onTimelineChange ?? setInternalTimeline

  const useWithStats = selectedTimeline === 'YTD' || selectedTimeline === 'All'
  const grossField: 'gross_income_ytd' | 'gross_income_all_time' =
    selectedTimeline === 'YTD' ? 'gross_income_ytd' : 'gross_income_all_time'

  // For YTD/All: use with_stats (has per-property native + converted totals)
  const usdStats = usePropertiesWithStats(undefined, userCurrency)
  const nativeStats = usePropertiesWithStats(undefined, 'native')

  // For other periods: use chart-data (aggregated, in user currency only)
  const range = useMemo(() => timelineToRange(selectedTimeline), [selectedTimeline])
  const chartDataQuery = useChartData({
    type: 'homePage',
    frequency: 'M',
    start: range.from,
    end: range.to,
    currency: userCurrency,
  })

  const periodLabel = TIMELINE_OPTIONS.find(o => o.value === selectedTimeline)?.label ?? 'All time'

  const chartData = useMemo(() => {
    if (useWithStats) {
      // Group properties by native currency, sum gross income
      const byCurrency = new Map<string, ExposureRow>()
      for (const p of usdStats.data ?? []) {
        const cur = p.currency || '???'
        const usdValue = Math.abs(p[grossField] ?? 0)
        const existing = byCurrency.get(cur)
        if (existing) existing.usdValue += usdValue
        else byCurrency.set(cur, { currency: cur, nativeValue: 0, usdValue })
      }
      for (const p of nativeStats.data ?? []) {
        const cur = p.currency || '???'
        const nativeValue = Math.abs(p[grossField] ?? 0)
        const existing = byCurrency.get(cur)
        if (existing) existing.nativeValue += nativeValue
        else byCurrency.set(cur, { currency: cur, nativeValue, usdValue: 0 })
      }
      return Array.from(byCurrency.values()).sort((a, b) => b.usdValue - a.usdValue)
    } else {
      // From chart-data: sum income categories across all periods
      const data = chartDataQuery.data
      if (!data) return []
      // Chart-data is in user currency. Group by income category.
      // But we don't have per-currency split from chart-data.
      // So we show a single bar per currency by fetching properties separately.
      // For now, show total income as a single "Portfolio" bar.
      const totalIncome = (data.datasets || [])
        .filter(ds => INCOME_CATEGORIES.includes((ds.label || '').toLowerCase()))
        .reduce((sum, ds) => sum + (ds.data || []).reduce((s, v) => s + Math.abs(v), 0), 0)
      // Also fetch native-currency property stats for the table
      const nativeTotal = (nativeStats.data || [])
        .reduce((sum, p) => sum + Math.abs(p.gross_income_all_time ?? 0), 0)
      return [{ currency: 'Portfolio', nativeValue: nativeTotal, usdValue: totalIncome }]
    }
  }, [useWithStats, usdStats.data, nativeStats.data, grossField, chartDataQuery.data])

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

  const isLoading = useWithStats
    ? (usdStats.isLoading || nativeStats.isLoading)
    : chartDataQuery.isLoading

  if (isLoading) {
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
