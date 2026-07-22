// frontend/src/components/charts/TenantRentChart.tsx
//
// Tenant rent history bar chart (Plan C Task 9). Single-series BarChart
// of rent received per period for one tenant, with a Brush for long
// tenancies. Data comes from `useChartData({ type: 'tenant', elementId })`.
//
// Click a bar to drill into /transactions?tenant=...&period=... for the
// underlying transactions in that period.
//
// Task 22: the chart-data endpoint for a tenant returns a single dataset
// WITHOUT a `label`, which made the legend + table header show "Series 1".
// We override that fallback to "Rent" so the label is meaningful.
//
// Task 23: the table view now formats numbers with `formatNumber` and
// paginates via `PaginatedTable`.
import { useMemo, useState, type ReactNode } from 'react'
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
import { PaginatedTable } from './PaginatedTable'
import { transformForRecharts } from './_chartAdapter'
import { useChartData } from '@/api/charts'
import { formatCurrency, formatCurrencyAxis, formatNumber } from '@/lib/format'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

type Props = {
  // Default chart data (parent-supplied, typically monthly over the
  // lease lifetime). The timeline selector trims client-side.
  data: ReturnType<typeof useChartData>['data']
  onBarClick?: (period: string) => void
  // Optional currency override. The chart-data response carries its own
  // `currency` field; we fall back to that when the parent doesn't pass
  // one explicitly.
  currency?: string
}

// Timeline options — mirrors the dashboard's TIMELINE_OPTIONS.
const TIMELINE_OPTIONS = [
  { value: 'YTD', label: 'Year to date' },
  { value: '3m', label: 'Last 3 months' },
  { value: '6m', label: 'Last 6 months' },
  { value: '12m', label: 'Last 12 months' },
  { value: '3Y', label: 'Last 3 years' },
  { value: '5Y', label: 'Last 5 years' },
  { value: 'all', label: 'All history' },
] as const

type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function cutoffFor(timeline: Timeline): Date | null {
  if (timeline === 'all') return null
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

function parseMonthLabel(label: string): Date | null {
  const m = label.match(/^([A-Za-z]{3})-(\d{2,4})$/)
  if (!m) return null
  const monthIdx = MONTH_NAMES.indexOf(m[1])
  if (monthIdx < 0) return null
  let year = Number(m[2])
  if (year < 100) year += 2000
  return new Date(year, monthIdx, 1)
}

// Force a friendly label on the dataset before transformForRecharts
// replaces empty labels with "Series N". The tenant chart-data endpoint
// returns a single dataset without a label, so the legend + table header
// would otherwise read "Series 1".
function withRentLabel(data: Props['data']): Props['data'] {
  if (!data) return data
  return {
    ...data,
    datasets: data.datasets.map((ds, i) =>
      ds.label ? ds : { ...ds, label: i === 0 ? 'Rent' : ds.label ?? `Series ${i + 1}` },
    ),
  }
}

export function TenantRentChart({ data, onBarClick, currency }: Props) {
  const [timeline, setTimeline] = useState<Timeline>('all')
  const cutoff = useMemo(() => cutoffFor(timeline), [timeline])

  const labeledData = useMemo(() => withRentLabel(data), [data])
  const { chartData, series, currency: dataCurrency } = transformForRecharts(
    labeledData ?? { labels: [], datasets: [], currency: currency ?? '' },
  )
  const displayCurrency = currency ?? dataCurrency

  // Trim rows older than the cutoff (parent supplies monthly data over
  // the lease lifetime — wide enough to cover every option).
  const filteredChartData = useMemo(() => {
    if (!cutoff) return chartData
    return chartData.filter(row => {
      const d = parseMonthLabel(String(row.label))
      if (!d) return true
      return d >= cutoff
    })
  }, [chartData, cutoff])

  // Table payload — formatted amounts (Task 23 uses formatNumber so
  // large rents read with thousands separators; the chart axis/tooltip
  // still uses the currency formatter). PaginatedTable handles the
  // Prev/Next pagination.
  const tableData = {
    headers: ['Period', ...series.map(s => s.label)],
    rows: filteredChartData.map(row => [
      row.label as string,
      ...series.map(s => Number(row[s.key]) || 0),
    ]),
  }

  const controls: ReactNode = (
    <Select
      value={timeline}
      onValueChange={(v) => setTimeline(v as Timeline)}
    >
      <SelectTrigger className="h-8 w-[150px]" aria-label="Rent history timeline">
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
      title="Rent history"
      description={`Rent received per period${
        displayCurrency ? ` (${displayCurrency})` : ''
      }`}
      controls={controls}
      tableData={tableData}
      tableRenderer={
        <PaginatedTable
          headers={tableData.headers}
          rows={tableData.rows}
          formatRow={(row) => [
            String(row[0]),
            ...row.slice(1).map((v) => formatNumber(Number(v))),
          ]}
        />
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={filteredChartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          {/* Axis uses compact `k`; tooltip uses full `#,###` per spec. */}
          <YAxis tickFormatter={(v) => formatCurrencyAxis(v, displayCurrency)} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => formatCurrency(Number(v), displayCurrency)} />
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
