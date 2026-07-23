// frontend/src/components/charts/RentYieldChart.tsx
//
// Rent Yield line chart (Plan C Task 8). Shows TWO yield series per
// period:
//   * Gross Yield = annualised revenue / property value
//   * Net Yield   = annualised (revenue - expenses) / property value
// Both annualised (monthly × 12, quarterly × 4, yearly × 1) so the
// percentages are comparable across horizons.
//
// The chart-data endpoint for a property carries a `rent` series (and
// any other transaction categories); the property's value is taken from
// the latest PropertyValuation (or 1 if none exists, so the chart still
// renders without a divide-by-zero). Gross Yield sums income-category
// series; Net Yield subtracts expense-category series from that total.
//
// X-axis formatting: when the selected horizon spans more than 12
// months we collapse the per-month `Mon-yy` labels to `yyyy` so the
// axis stays readable. An info icon (ⓘ) next to the title carries the
// yield definition as a tooltip.
import { useMemo, useState, type ReactNode } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Info } from 'lucide-react'
import { ChartCard } from './ChartCard'
import { PaginatedTable } from './PaginatedTable'
import { transformForRecharts } from './_chartAdapter'
import { useChartData } from '@/api/charts'
import { usePropertyValuations } from '@/api/propertyValuations'
import { useProperty } from '@/api/properties'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip as UiTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { formatCurrency } from '@/lib/format'

// Income categories — mirrors `rentals/constants.py::INCOME_CATEGORIES`.
// Only `rent` is income; `cost_reimbursement` (formerly `other_income`)
// is an expense-category offset (positive amount that nets against the
// other expense categories).
const INCOME_CATEGORIES = ['rent']

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
  { value: 'All', label: 'All time' },
] as const

type Timeline = (typeof TIMELINE_OPTIONS)[number]['value']

// Approximate month count for each timeline — used to decide whether to
// collapse the X axis to year-only labels (`> 12 months`).
function timelineMonths(timeline: Timeline): number {
  switch (timeline) {
    case 'YTD':
      return Math.max(1, new Date().getMonth() + 1)
    case '3m':
      return 3
    case '6m':
      return 6
    case '12m':
      return 12
    case '3Y':
      return 36
    case '5Y':
      return 60
    case 'All':
      return Number.POSITIVE_INFINITY
  }
}

function timelineToRange(timeline: Timeline): { from: string; to: string } {
  const today = new Date()
  const to = today.toISOString().slice(0, 10)
  // `All` uses the backend's all-time sentinel `1900-01-01`.
  if (timeline === 'All') return { from: '1900-01-01', to }
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

// Parse a chart-data monthly label (`Jan-24`) into a `yyyy` string for
// the collapsed long-horizon axis. Returns the original label when it
// doesn't match the monthly pattern (e.g. already-yearly labels).
function toAxisLabel(label: string, collapseYears: boolean): string {
  if (!collapseYears) return label
  const m = label.match(/^([A-Za-z]{3})-(\d{2,4})$/)
  if (!m) return label
  let year = Number(m[2])
  if (year < 100) year += 2000
  return String(year)
}

export function RentYieldChart({ data, propertyId, currency: currencyProp }: Props) {
  const [timeline, setTimeline] = useState<Timeline>('5Y')
  const range = useMemo(() => timelineToRange(timeline), [timeline])
  const collapseYears = timelineMonths(timeline) > 12

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

  // Fetch the property directly so we can read its native currency for
  // display (T6). The parent may still pass `currency` as a fallback
  // (used while the property query is loading).
  const propertyQuery = useProperty(propertyId)
  const currency = currencyProp ?? propertyQuery.data?.currency ?? ''

  const valuations = usePropertyValuations(propertyId)

  // Latest valuation = highest capital_structure_date. T6: the property
  // value comes from the latest `Property_capital_structure` entry's
  // `capital_structure_value`. If no valuations exist, we render an
  // explicit "No valuation data" state instead of dividing by a
  // synthetic 1 (which previously produced a flat yield of rent / 1 —
  // misleading because the percentages were gigantic for any real rent).
  const latestValue = useMemo(() => {
    const list = valuations.data ?? []
    if (list.length === 0) return null
    const latest = [...list].sort((a, b) =>
      a.capital_structure_date < b.capital_structure_date ? 1 : -1,
    )[0]
    const parsed = Number(latest?.capital_structure_value)
    if (!Number.isFinite(parsed) || parsed <= 0) return null
    return parsed
  }, [valuations.data])
  const hasValuation = latestValue !== null
  const value = hasValuation ? (latestValue as number) : 0

  const { chartData, series } = transformForRecharts(
    effectiveData ?? { labels: [], datasets: [], currency: currency ?? '' },
  )

  // Split series into income vs expense so we can compute gross and net
  // yield independently. Gross = sum of income series; Net = gross minus
  // the absolute value of expense series (expenses come back negative,
  // so subtracting them ADDS their magnitude to the denominator's
  // numerator reduction — i.e. net = gross + expenses, where expenses
  // are already negative).
  const isIncome = (label: string) => INCOME_CATEGORIES.includes(label)
  const incomeSeries = series.filter((s) => isIncome(s.label))
  const expenseSeries = series.filter((s) => !isIncome(s.label))

  const yieldData = chartData.map(row => {
    const gross = incomeSeries.reduce(
      (acc, s) => acc + (Number(row[s.key]) || 0),
      0,
    )
    const expenses = expenseSeries.reduce(
      (acc, s) => acc + (Number(row[s.key]) || 0),
      0,
    )
    const grossAnnualised = gross * 12
    // expenses is already negative; gross + expenses = gross - |expenses|.
    const netAnnualised = (gross + expenses) * 12
    return {
      label: row.label as string,
      axisLabel: toAxisLabel(String(row.label), collapseYears),
      grossYield: value > 0 ? (grossAnnualised / value) * 100 : 0,
      netYield: value > 0 ? (netAnnualised / value) * 100 : 0,
    }
  })

  // Table payload — gross + net yield per period. ChartCard wraps it in
  // the Table/Chart toggle; PaginatedTable handles pagination.
  const tableData = {
    headers: ['Period', 'Gross yield %', 'Net yield %'],
    rows: yieldData.map(row => [
      row.label,
      Number(row.grossYield.toFixed(2)),
      Number(row.netYield.toFixed(2)),
    ]),
  }

  const controls: ReactNode = (
    <>
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
      {/* Yield definition tooltip — clickable/hoverable info icon next
          to the timeline selector. */}
      <TooltipProvider>
        <UiTooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label="Yield definition"
              className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-muted"
            >
              <Info className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            Gross Yield = annualised gross rent ÷ property value.
            Net Yield = (rent − expenses) ÷ property value.
          </TooltipContent>
        </UiTooltip>
      </TooltipProvider>
    </>
  )

  if (valuations.isLoading) {
    return (
      <ChartCard
        title="Rent yield"
        description={`Gross & net yield per period (${currency ?? ''})`}
        controls={controls}
        tableData={tableData}
        tableRenderer={
          <PaginatedTable
            headers={tableData.headers}
            rows={tableData.rows}
            formatRow={(row) => [
              String(row[0]),
              `${Number(row[1]).toFixed(2)}%`,
              `${Number(row[2]).toFixed(2)}%`,
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

  // T6: no valuation data -> the yield denominator is unknown, so any
  // percentage we rendered would be meaningless (previously the chart
  // silently fell back to value=1, producing gigantic rent/1 percentages
  // that looked like real data). Show an explicit empty state instead.
  if (!hasValuation) {
    return (
      <ChartCard
        title="Rent yield"
        description={`Gross & net yield per period (${currency ?? ''})`}
        controls={controls}
      >
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          No valuation data
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard
      title="Rent yield"
      description={`Gross & net yield per period (value: ${formatCurrency(
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
            `${Number(row[2]).toFixed(2)}%`,
          ]}
        />
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={yieldData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="axisLabel" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v) => formatPercent(Number(v))} tick={{ fontSize: 12 }} />
          <Tooltip
            formatter={(v) => formatPercent(Number(v))}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as { label?: string } | undefined
              return row?.label ?? ''
            }}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="grossYield"
            name="Gross yield"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="netYield"
            name="Net yield"
            stroke="#f97316"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
