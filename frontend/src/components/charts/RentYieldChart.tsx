// frontend/src/components/charts/RentYieldChart.tsx
//
// Rent Yield line chart (Plan C Task 8). Shows TWO yield series per
// period:
//   * Gross Yield = annualised revenue / property value
//   * Net Yield   = annualised (revenue - expenses) / property value
// Both annualised (monthly × 12) so the percentages are comparable
// across horizons.
//
// IMPORTANT (the "gross yield still zero" bug): the chart-data endpoint
// for `type='property'` only emits `Debt` + `Equity` datasets — it does
// NOT emit per-category totals (see the note in
// `PropertyDetailPage::pnlRows` and the backend
// `services/charts.py::get_chart_data` property branch). The previous
// implementation tried to filter a `rent` series out of that payload,
// found nothing, and silently rendered flat-zero yield lines. The fix
// is to derive rent + expenses directly from the property's
// transactions (already loaded by the detail page; we accept the same
// `transactions` prop instead of re-fetching chart-data) and bucket
// them per period.
//
// The property's value is taken from the latest PropertyValuation's
// `capital_structure_value`. DRF serialises Decimals as strings, so we
// parse with `Number()` before arithmetic (the previous code already
// did this, but we keep the guard explicit). If no usable valuation
// exists, we render an explicit empty state instead of dividing by a
// synthetic 1.
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
import { usePropertyValuations } from '@/api/propertyValuations'
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
import type { Transaction } from '@/types/transaction'

// Income categories — mirrors `rentals/constants.py::INCOME_CATEGORIES`.
// Only `rent` is income; `cost_reimbursement` (formerly `other_income`)
// is an expense-category offset (positive amount that nets against the
// other expense categories).
const INCOME_CATEGORIES = ['rent']

type Props = {
  // Pre-fetched transactions for this property. The chart buckets them
  // per period (year / quarter / month) to compute gross + net yield.
  // The parent already loads these for the P&L card; passing them in
  // avoids a second round-trip and keeps the source of truth single.
  transactions: Transaction[]
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

function timelineToRange(timeline: Timeline): { from: Date; to: Date } {
  const today = new Date()
  const to = today
  if (timeline === 'All') {
    // Sentinel start: any date earlier than the first transaction will
    // include everything; we use 1900-01-01 (matches the backend's
    // all-time sentinel).
    const from = new Date('1900-01-01')
    return { from, to }
  }
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
  return { from, to }
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return '—'
  return `${value.toFixed(1)}%`
}

// Render a chart-data period label. We emit monthly `Mon-yy` for <= 12
// months and yearly `yyyy` for longer horizons.
function periodLabel(d: Date, monthly: boolean): string {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  if (monthly) {
    const yy = String(d.getFullYear()).slice(-2)
    return `${months[d.getMonth()]}-${yy}`
  }
  return String(d.getFullYear())
}

// Generate the per-period anchor dates for the chart. Mirrors the
// backend's `chart_dates` windowing (calendar months for `M`, calendar
// years for `Y`). Monthly buckets use the first day of each month;
// yearly buckets use Jan 1 of each year.
function bucketAnchors(from: Date, to: Date, monthly: boolean): Date[] {
  const out: Date[] = []
  if (monthly) {
    const cursor = new Date(from.getFullYear(), from.getMonth(), 1)
    const end = new Date(to.getFullYear(), to.getMonth(), 1)
    while (cursor <= end) {
      out.push(new Date(cursor))
      cursor.setMonth(cursor.getMonth() + 1)
    }
  } else {
    const startYear = from.getFullYear()
    const endYear = to.getFullYear()
    for (let y = startYear; y <= endYear; y++) {
      out.push(new Date(y, 0, 1))
    }
  }
  // Cap to a sane maximum so the "All" horizon doesn't try to render
  // decades of monthly buckets. 120 points covers 10 years of monthly
  // data or 120 years of yearly data — both well past realistic use.
  return out.slice(-120)
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

export function RentYieldChart({ transactions, propertyId, currency: currencyProp }: Props) {
  const [timeline, setTimeline] = useState<Timeline>('5Y')
  const range = useMemo(() => timelineToRange(timeline), [timeline])
  const monthly = timelineMonths(timeline) <= 12
  const collapseYears = !monthly

  const valuations = usePropertyValuations(propertyId)
  const currency = currencyProp ?? ''

  // Latest valuation = highest capital_structure_date. The property
  // value comes from the latest `Property_capital_structure` entry's
  // `capital_structure_value`. DRF returns decimals as strings, so we
  // parse via `Number()` (NaN-safe). If no valuations exist (or the
  // value is non-positive / unparseable), we render an explicit
  // "No valuation data" state instead of dividing by a synthetic 1
  // (which previously produced gigantic rent/1 percentages that
  // masqueraded as real data).
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

  // Bucket transactions per period (month for <= 12m horizons, year for
  // longer horizons). Rent category => income; everything else =>
  // expense (expenses come back negative from the serializer, so
  // summing the raw amount already nets them out).
  const yieldData = useMemo(() => {
    const isIncome = (cat: string) => INCOME_CATEGORIES.includes(cat)
    const anchors = bucketAnchors(range.from, range.to, monthly)
    return anchors.map((anchor) => {
      let gross = 0
      let expenses = 0
      for (const t of transactions) {
        const amount = Number(t.amount)
        if (!Number.isFinite(amount)) continue
        const d = new Date(t.date)
        if (Number.isNaN(d.getTime())) continue
        // Bucket key: same year (and same month when monthly).
        const samePeriod = monthly
          ? d.getFullYear() === anchor.getFullYear() &&
            d.getMonth() === anchor.getMonth()
          : d.getFullYear() === anchor.getFullYear()
        if (!samePeriod) continue
        if (isIncome(t.category || '')) gross += amount
        else expenses += amount // already negative for expenses
      }
      // Annualisation factor: monthly × 12, yearly × 1.
      const annualFactor = monthly ? 12 : 1
      const grossAnnualised = gross * annualFactor
      // expenses is already negative; gross + expenses = gross - |expenses|.
      const netAnnualised = (gross + expenses) * annualFactor
      const label = periodLabel(anchor, monthly)
      return {
        label,
        axisLabel: toAxisLabel(label, collapseYears),
        grossYield: value > 0 ? (grossAnnualised / value) * 100 : 0,
        netYield: value > 0 ? (netAnnualised / value) * 100 : 0,
      }
    })
  }, [transactions, range.from, range.to, monthly, collapseYears, value])

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
        description={`Gross & net yield per period (${currency})`}
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

  // No valuation data -> the yield denominator is unknown, so any
  // percentage we rendered would be meaningless (previously the chart
  // silently fell back to value=1, producing gigantic rent/1 percentages
  // that looked like real data). Show an explicit empty state instead.
  if (!hasValuation) {
    return (
      <ChartCard
        title="Rent yield"
        description={`Gross & net yield per period (${currency})`}
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
        currency,
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
