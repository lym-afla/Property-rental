// frontend/src/components/charts/OccupancyChart.tsx
//
// Stacked area chart (Plan C Task 6) showing occupied vs vacant units
// over time. Data is derived client-side from the active tenants list
// (`lease_start` <= period end AND (no `lease_end` OR `lease_end` >=
// period start)) and the total property count, bucketed monthly.
//
// The bucket set is generated from the union of lease_start / today so
// the chart always spans the tenant history; properties with no tenants
// still appear as a baseline vacant band.
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

// Build a sorted, de-duplicated list of `YYYY-MM` month buckets covering
// every tenant's lease_start through today.
function buildMonthBuckets(dates: string[]): string[] {
  const set = new Set<string>()
  const today = new Date()
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
  set.add(todayKey)
  for (const d of dates) {
    if (!d) continue
    const dt = new Date(d)
    if (Number.isNaN(dt.getTime())) continue
    set.add(`${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`)
  }
  return Array.from(set).sort()
}

function monthKeyOf(dateStr: string): string | null {
  if (!dateStr) return null
  const dt = new Date(dateStr)
  if (Number.isNaN(dt.getTime())) return null
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}`
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

    let buckets = buildMonthBuckets(tenantList.map(t => t.lease_start))
    // Trim to the last `monthsBack` months when a finite window is
    // requested. Buckets are sorted ascending, so slice from the end.
    if (monthsBack !== undefined && monthsBack > 0) {
      buckets = buckets.slice(-monthsBack)
    }
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
