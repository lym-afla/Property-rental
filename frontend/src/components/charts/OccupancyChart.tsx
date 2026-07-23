// frontend/src/components/charts/OccupancyChart.tsx
//
// Stacked area chart (Plan C Task 6) showing occupied vs vacant units
// over time. Data is derived client-side from the active tenants list
// (`lease_start` <= period end AND (no `lease_end` OR `lease_end` >=
// period start)) and the total property count, bucketed monthly.
//
// The bucket set is generated as a CONTINUOUS monthly range so the
// timeline selector actually changes the data: for a finite `monthsBack`
// we walk back N months from today; for `undefined` we span from the
// earliest lease_start through today. Generating every month in the
// window (instead of only months that appear as a lease_start) means
// picking "Last 24 months" vs "Last 12 months" produces a visibly
// different x-axis even when leases are sparse.
import { useMemo } from 'react'
import type { ReactNode } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { ChartCard } from './ChartCard'
import { useProperties } from '@/api/properties'
import { useTenants } from '@/api/tenants'

function monthKeyOf(dateStr: string): string | null {
  if (!dateStr) return null
  const dt = new Date(dateStr)
  if (Number.isNaN(dt.getTime())) return null
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`
}

// Generate a continuous list of `YYYY-MM` month keys covering the
// requested window ending at the current month. `monthsBack` undefined
// => span from `earliestStart` (the earliest lease_start in the tenant
// set) through today.
function buildMonthBuckets(
  monthsBack: number | undefined,
  earliestStart: string | null,
): string[] {
  const today = new Date()
  const end = new Date(today.getFullYear(), today.getMonth(), 1)
  let start: Date
  if (monthsBack && monthsBack > 0) {
    start = new Date(end.getFullYear(), end.getMonth() - (monthsBack - 1), 1)
  } else if (earliestStart) {
    const dt = new Date(earliestStart)
    start = Number.isNaN(dt.getTime())
      ? new Date(end.getFullYear(), end.getMonth() - 11, 1)
      : new Date(dt.getFullYear(), dt.getMonth(), 1)
  } else {
    // No tenants and no explicit window: default to last 12 months so
    // the chart still renders a vacant baseline rather than a single
    // point.
    start = new Date(end.getFullYear(), end.getMonth() - 11, 1)
  }
  const keys: string[] = []
  const cur = new Date(start)
  while (cur <= end) {
    keys.push(
      `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, '0')}`,
    )
    cur.setMonth(cur.getMonth() + 1)
  }
  return keys
}

// A tenant is "active" during a `YYYY-MM` bucket when their lease_start
// is in or before that month AND (lease_end is null OR lease_end is in
// or after that month). We compare on the YYYY-MM string directly —
// lexicographic ordering matches chronological for ISO month keys.
function leaseActiveIn(
  bucket: string,
  leaseStart: string,
  leaseEnd: string | null,
): boolean {
  const startKey = monthKeyOf(leaseStart)
  if (!startKey || startKey > bucket) return false
  if (leaseEnd) {
    const endKey = monthKeyOf(leaseEnd)
    if (endKey && endKey < bucket) return false
  }
  return true
}

type Props = {
  // How many months of history to show. `undefined` means "all history"
  // (the full tenant lease span). Defaults to undefined for backwards
  // compatibility; the dashboard passes an explicit value.
  monthsBack?: number
  // Optional controls rendered in the card header (e.g. a period Select).
  controls?: ReactNode
}

export function OccupancyChart({ monthsBack, controls }: Props = {}) {
  const properties = useProperties()
  const tenants = useTenants()

  const chartData = useMemo(() => {
    const tenantList = tenants.data ?? []
    const totalUnits = properties.data?.length ?? 0

    // Earliest lease_start drives the "all history" span.
    let earliestStart: string | null = null
    for (const t of tenantList) {
      if (!t.lease_start) continue
      if (earliestStart === null || t.lease_start < earliestStart) {
        earliestStart = t.lease_start
      }
    }

    const buckets = buildMonthBuckets(monthsBack, earliestStart)
    return buckets.map(bucket => {
      const occupied = tenantList.filter(t =>
        leaseActiveIn(bucket, t.lease_start, t.lease_end),
      ).length
      return {
        label: bucket,
        Occupied: occupied,
        Vacant: Math.max(0, totalUnits - occupied),
      }
    })
  }, [properties.data, tenants.data, monthsBack])

  const tableData = useMemo(
    () => ({
      headers: ['Period', 'Occupied', 'Vacant'],
      rows: chartData.map(row => [row.label, row.Occupied, row.Vacant]),
    }),
    [chartData],
  )

  if (properties.isLoading || tenants.isLoading) {
    return (
      <ChartCard title="Occupancy" description="Occupied vs vacant units over time" controls={controls}>
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      </ChartCard>
    )
  }

  return (
    <ChartCard title="Occupancy" description="Occupied vs vacant units over time" controls={controls} tableData={tableData}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="occupiedGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="vacantGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#94a3b8" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#94a3b8" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Area
            type="monotone"
            dataKey="Occupied"
            stackId="1"
            stroke="#22c55e"
            fill="url(#occupiedGradient)"
          />
          <Area
            type="monotone"
            dataKey="Vacant"
            stackId="1"
            stroke="#94a3b8"
            fill="url(#vacantGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
