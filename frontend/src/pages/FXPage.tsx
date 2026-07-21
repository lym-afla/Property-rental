// frontend/src/pages/FXPage.tsx
//
// FX rates summary page.
//
// The raw `/api/v1/fx/` payload is one row per (pair, date) snapshot —
// hundreds of rows that are uninformative to scroll through. This page
// collapses that history to the LATEST rate observed for each currency
// pair (group by from_currency/to_currency, take the most recent date),
// plus the inverse rate for quick reference.
//
//   - `useFX()` for the underlying rows.
//   - `useUpdateFX()` mutation wired to the "Update FX" button. The hook
//     POSTs `/api/v1/fx/update/`, which refetches yfinance rates for every
//     property owned by the requester; on success it invalidates `fx.all`,
//     `transactions.all`, and `chartData.all` (FX-derived amounts are stale).
//   - `DataTable`, `SkeletonTable`, `EmptyState`, `ErrorState`.
//
// The page is read-only — the spec does not call for create/edit/delete on
// FX rates (they're system-derived), so the only mutation affordance is the
// "Update FX" refresh button in the header.
import { useMemo } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { useFX, useUpdateFX } from '@/api/fx'
import { DataTable } from '@/components/table/DataTable'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/format'
import type { FX } from '@/types/fx'

// One row per currency pair: the most recent snapshot for that pair plus
// the inverse rate (1 / rate) for at-a-glance conversion in both directions.
// `id` is a synthetic 1-based index so the row satisfies DataTable's
// `{ id: number }` constraint (the underlying FX rows have their own ids,
// but a pair has many — we only surface the latest snapshot here).
type LatestRate = {
  id: number
  pair: string
  from_currency: string
  to_currency: string
  rate: string
  date: string
  inverse: string
}

// Collapse the raw FX history to the latest snapshot per currency pair.
// Dates are ISO `YYYY-MM-DD` strings, so lexicographic comparison matches
// chronological order — no Date parsing needed. Ties on the same date keep
// the last row seen, which is stable enough for a derived summary tile.
function latestRatePerPair(rows: FX[]): LatestRate[] {
  const latest = new Map<string, FX>()
  for (const row of rows) {
    const key = `${row.from_currency}/${row.to_currency}`
    const prev = latest.get(key)
    if (!prev || row.date >= prev.date) {
      latest.set(key, row)
    }
  }
  return Array.from(latest.entries())
    .map(([key, row], idx) => {
      const rateNum = Number(row.rate)
      const inverse =
        Number.isFinite(rateNum) && rateNum !== 0
          ? (1 / rateNum).toFixed(4)
          : '—'
      return {
        id: idx + 1,
        pair: key,
        from_currency: row.from_currency,
        to_currency: row.to_currency,
        rate: row.rate,
        date: row.date,
        inverse,
      }
    })
    .sort((a, b) => a.pair.localeCompare(b.pair))
}

export function FXPage() {
  const { data, isLoading, isError, refetch } = useFX()
  const updateFX = useUpdateFX()

  const summary = useMemo(() => (data ? latestRatePerPair(data) : []), [data])

  const columns: ColumnDef<LatestRate>[] = [
    {
      accessorKey: 'pair',
      header: 'Pair',
      cell: ({ row }) => (
        <span className="font-medium">
          {row.original.from_currency} → {row.original.to_currency}
        </span>
      ),
    },
    {
      accessorKey: 'rate',
      header: 'Rate',
      // The serializer returns the rate as a stringified decimal; display
      // it verbatim (no rounding) so users see exactly what the backend
      // stored. The rate itself lives in its own `<span>` (rather than a
      // composite text node) so screen readers and tests can target the
      // numeric value directly.
      cell: ({ row }) => (
        <span className="font-mono">
          1 {row.original.from_currency} ={' '}
          <span data-testid="rate-value">{row.original.rate}</span>{' '}
          {row.original.to_currency}
        </span>
      ),
    },
    {
      accessorKey: 'inverse',
      header: 'Inverse',
      cell: ({ row }) => (
        <span className="font-mono text-muted-foreground">
          1 {row.original.to_currency} = {row.original.inverse}{' '}
          {row.original.from_currency}
        </span>
      ),
    },
    {
      accessorKey: 'date',
      header: 'Date',
      sortingFn: 'datetime',
      cell: ({ row }) => formatDate(row.original.date),
    },
  ]

  if (isLoading) {
    return <SkeletonTable />
  }

  if (isError) {
    return (
      <ErrorState message="Failed to load FX rates" onRetry={() => refetch()} />
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="No FX rates yet"
          description="Refresh rates from yfinance to populate the table."
          actionLabel="Update FX"
          onAction={() =>
            updateFX.mutate(undefined, {
              onSuccess: () => toast.success('FX rates updated'),
              onError: () => toast.error('Failed to update FX rates'),
            })
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">FX Rates</h1>
          <p className="text-sm text-muted-foreground">
            Latest rate per currency pair ({summary.length}{' '}
            {summary.length === 1 ? 'pair' : 'pairs'}).
          </p>
        </div>
        <Button
          onClick={() =>
            updateFX.mutate(undefined, {
              onSuccess: () => toast.success('FX rates updated'),
              onError: () => toast.error('Failed to update FX rates'),
            })
          }
          disabled={updateFX.isPending}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          {updateFX.isPending ? 'Updating…' : 'Update FX'}
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={summary}
        initialSorting={[{ id: 'pair', desc: false }]}
      />
    </div>
  )
}
