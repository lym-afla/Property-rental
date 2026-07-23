// frontend/src/components/charts/ValuationChart.tsx
//
// Property Valuation combo chart (Plan C Task 8). Stacked bar (Debt +
// Equity) plus a Line overlay showing total property value over time.
//
// The chart-data endpoint for a property returns Debt + Equity series
// (see `ChartDataView`); transformForRecharts maps those onto rows. The
// "total" trajectory line is just the per-period sum of those two — i.e.
// the property value itself — drawn as a Line overlay so users can see
// the bar composition *and* the value trend in a single panel.
//
// Task 19: a time-horizon selector lets the user re-scope the window
// (the parent supplies 5Y of monthly data, which subsumes every shorter
// horizon — we trim client-side rather than re-fetching), and the
// description surfaces the property's native currency.
//
// Click a bar to drill into /transactions?... for that period.
import { useMemo, useState, type ReactNode } from 'react'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { transformForRecharts } from './_chartAdapter'
import { useChartData } from '@/api/charts'
import { formatCurrency, formatCurrencyAxis } from '@/lib/format'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type Props = {
  // Default chart data (parent-supplied — typically 5Y monthly). The
  // timeline selector trims this client-side; no extra round-trip is
  // fired because the parent window already covers every option.
  data: ReturnType<typeof useChartData>['data']
  onBarClick?: (period: string) => void
  // The property's native currency (Task 19). Forwarded by the parent so
  // the description + axis carry the right symbol.
  currency?: string
}

// Timeline options — mirrors the dashboard's TIMELINE_OPTIONS. "All"
// keeps every row (the parent request already spans 5Y, and the
// ValuationChart filters client-side; "All" simply disables the cutoff).
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

// Earliest row date we want to keep for a given timeline (rows older
// than this are dropped before charting). Returns `null` for "All" so
// the caller knows to skip the cutoff entirely. The parent request is
// 5Y monthly, so trimming covers every finite option without a refetch.
function cutoffFor(timeline: Timeline): Date | null {
  if (timeline === 'All') return null
  const today = new Date()
  const cutoff = new Date(today)
  switch (timeline) {
    case 'YTD':
      cutoff.setMonth(0, 1)
      break
    case '3m':
      cutoff.setMonth(cutoff.getMonth() - 3)
      break
    case '6m':
      cutoff.setMonth(cutoff.getMonth() - 6)
      break
    case '12m':
      cutoff.setFullYear(cutoff.getFullYear() - 1)
      break
    case '3Y':
      cutoff.setFullYear(cutoff.getFullYear() - 3)
      break
    case '5Y':
      cutoff.setFullYear(cutoff.getFullYear() - 5)
      break
  }
  return cutoff
}

// Parse a chart-data monthly label (`Jan-24`) into a Date for cutoff
// filtering. Non-monthly labels are kept verbatim (returned as null so
// the caller can short-circuit).
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
function parseMonthLabel(label: string): Date | null {
  const m = label.match(/^([A-Za-z]{3})-(\d{2,4})$/)
  if (!m) return null
  const monthIdx = MONTH_NAMES.indexOf(m[1])
  if (monthIdx < 0) return null
  let year = Number(m[2])
  if (year < 100) year += 2000
  return new Date(year, monthIdx, 1)
}

export function ValuationChart({ data, onBarClick, currency }: Props) {
  const [timeline, setTimeline] = useState<Timeline>('5Y')
  const cutoff = useMemo(() => cutoffFor(timeline), [timeline])

  const { chartData, series, currency: dataCurrency } = transformForRecharts(
    data ?? { labels: [], datasets: [], currency: currency ?? '' },
  )
  const displayCurrency = currency ?? dataCurrency

  // Augment each row with a synthetic `value` field = Debt + Equity (or
  // whichever series the backend happened to send). ComposedChart can
  // then render the same row both as stacked bars and as a line.
  const enrichedData = chartData
    .map((row): Record<string, number | string> => {
      const total = series.reduce(
        (acc, s) => acc + (Number(row[s.key]) || 0),
        0,
      )
      return { ...row, value: total }
    })
    .filter(row => {
      // "All time" disables the cutoff — keep every row.
      if (cutoff === null) return true
      const labelDate = parseMonthLabel(String(row.label))
      // Keep non-monthly labels (e.g. yearly aggregates) as-is.
      if (!labelDate) return true
      return labelDate >= cutoff
    })

  const tableData = {
    headers: ['Period', ...series.map(s => s.label), 'Value'],
    rows: enrichedData.map(row => [
      row.label as string,
      ...series.map(s => row[s.key] as number),
      row.value as number,
    ]),
  }

  const controls: ReactNode = (
    <Select
      value={timeline}
      onValueChange={(v) => setTimeline(v as Timeline)}
    >
      <SelectTrigger className="h-8 w-[150px]" aria-label="Valuation timeline">
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

  return (
    <ChartCard
      title="Valuation"
      description={`Debt + Equity stacked, total value overlay${
        displayCurrency ? ` (${displayCurrency})` : ''
      }`}
      controls={controls}
      tableData={tableData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={enrichedData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, displayCurrency)} tick={{ fontSize: 12 }} />
          {/* Axis uses compact `k`; tooltip uses full `#,###` per spec. */}
          <Tooltip formatter={(v) => formatCurrency(Number(v), displayCurrency)} />
          <Legend />
          {series.map(s => (
            <Bar
              key={s.key}
              dataKey={s.key}
              name={s.label}
              stackId="valuation"
              fill={s.color}
              onClick={(payload: any) => onBarClick?.(payload.label)}
              cursor={onBarClick ? 'pointer' : 'default'}
            />
          ))}
          <Line
            type="monotone"
            dataKey="value"
            name="Total value"
            stroke="#0f172a"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
