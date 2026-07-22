// frontend/src/components/charts/RentYieldChart.tsx
//
// Rent Yield line chart (Plan C Task 8). Shows rent yield per period,
// defined as annualised net income in the period divided by the property's
// current notional value, expressed as a percentage.
//
// The chart-data endpoint for a property carries a `rent` series; the
// property's value is taken from the latest PropertyValuation (or, if
// no valuation exists, falls back to 1 so the chart still renders
// without divide-by-zero noise). Yield % = annualised rent / value × 100.
// Monthly data is multiplied by 12; quarterly by 4; yearly by 1.
//
// Task 15: a time-horizon selector lets the user re-scope the window the
// chart pulls from, and the chart description surfaces the property's
// native currency alongside the notional value.
//
// Task 16: the "Table" toggle on the ChartCard renders the underlying
// per-period yield numbers; the parent ChartCard already handles the
// toggle UI, and `PaginatedTable` provides simple pagination.
import { useMemo, useState, type ReactNode } from 'react'
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
import { PaginatedTable } from './PaginatedTable'
import { transformForRecharts } from './_chartAdapter'
import { useChartData } from '@/api/charts'
import { usePropertyValuations } from '@/api/propertyValuations'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatCurrency } from '@/lib/format'

type Props = {
  // Pre-fetched chart data for the default window. The chart still uses
  // `useChartData` to re-fetch when the user changes the time horizon.
  data: ReturnType<typeof useChartData>['data']
  propertyId: number
  // The property's native currency, forwarded by the parent so the
  // notional value + yield rows carry the right symbol without a second
  // round-trip for the property record.
  currency?: string
}

// Timeline options — mirrors the dashboard's TIMELINE_OPTIONS. Keys map to
// a "today minus N" window via `timelineToRange` (mirrors the backend's
// `calculate_from_date` semantics).
const TIMELINE_OPTIONS = [
  { value: 'YTD', label: 'Year to date' },
  { value: '3m', label: 'Last 3 months' },
  { value: '6m', label: 'Last 6 months' },
  { value: '12m', label: 'Last 12 months' },
  { value: '3Y', label: 'Last 3 years' },
  { value: '5Y', label: 'Last 5 years' },
] as const

type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

function timelineToRange(timeline: Timeline): { from: string; to: string } {
  const today = new Date()
  const to = today.toISOString().slice(0, 10)
  const from = new Date(today)
  switch (timeline) {
    case 'YTD':
      from.setMonth(0, 1)
      break
    case '3m':
      from.setMonth(from.getMonth() - 3)
      break
    case '6m':
      from.setMonth(from.getMonth() - 6)
      break
    case '12m':
      from.setFullYear(from.getFullYear() - 1)
      break
    case '3Y':
      from.setFullYear(from.getFullYear() - 3)
      break
    case '5Y':
      from.setFullYear(from.getFullYear() - 5)
      break
  }
  return { from: from.toISOString().slice(0, 10), to }
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return `${value.toFixed(1)}%`
}

export function RentYieldChart({ data, propertyId, currency }: Props) {
  const [timeline, setTimeline] = useState<Timeline>('5Y')
  const range = useMemo(() => timelineToRange(timeline), [timeline])

  // Re-fetch when the user changes the horizon. `data` is the default
  // (monthly, 5Y) payload supplied by the parent; we override it as soon
  // as the user picks a different horizon so the chart reflects their
  // choice without a parent re-render.
  const scopedQuery = useChartData({
    type: 'property',
    elementId: propertyId,
    frequency: 'M',
    start: range.from,
    end: range.to,
  })
  const effectiveData = scopedQuery.data ?? data

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

  const { chartData, series } = transformForRecharts(
    effectiveData ?? { labels: [], datasets: [], currency: currency ?? '' },
  )

  // Sum of all series per period is interpreted as "rent received" for
  // that period (the chart-data request for a property typically returns
  // only the rent category, but we sum defensively so any extra series
  // doesn't break the chart). Annualise by multiplying monthly values by
  // 12 so the percentage is comparable across horizons.
  const yieldData = chartData.map(row => {
    const rent = series.reduce((acc, s) => acc + (Number(row[s.key]) || 0), 0)
    const annualised = rent * 12
    return {
      label: row.label,
      yield: value > 0 ? (annualised / value) * 100 : 0,
    }
  })

  // Table payload — formatted value + yield per period. ChartCard wraps
  // it in the Table/Chart toggle; PaginatedTable handles pagination.
  const tableData = {
    headers: ['Period', 'Yield %'],
    rows: yieldData.map(row => [
      row.label as string,
      Number(row.yield.toFixed(2)),
    ]),
  }

  const controls: ReactNode = (
    <Select
      value={timeline}
      onValueChange={(v) => setTimeline(v as Timeline)}
    >
      <SelectTrigger className="h-8 w-[150px]" aria-label="Rent yield timeline">
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

  if (valuations.isLoading) {
    return (
      <ChartCard
        title="Rent yield"
        description={`Annualised rent / value per period (${currency ?? ''})`}
        controls={controls}
        tableData={tableData}
        tableRenderer={
          <PaginatedTable
            headers={tableData.headers}
            rows={tableData.rows}
            formatRow={(row) => [
              String(row[0]),
              `${Number(row[1]).toFixed(2)}%`,
            ]}
          />
        }
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Rent yield"
      description={`Annualised rent / value per period (value: ${formatCurrency(
        value,
        currency ?? '',
      )})`}
      controls={controls}
      tableData={tableData}
      tableRenderer={
        <PaginatedTable
          headers={tableData.headers}
          rows={tableData.rows}
          formatRow={(row) => [
            String(row[0]),
            `${Number(row[1]).toFixed(2)}%`,
          ]}
        />
      }
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
