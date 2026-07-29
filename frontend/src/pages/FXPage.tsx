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
// Task 11: a date picker scopes the "latest" computation. When a date is
// selected, the page shows the most recent rate observed AT OR BEFORE
// that date for each pair (so users can answer "what was the EUR/USD
// rate on 2024-03-15?"). Pagination is removed — the summary is short
// enough to fit a single page, and the underlying detail lives in the
// admin / Transactions page anyway.
//
//   - `useFX()` for the underlying rows.
//   - `useUpdateFX()` mutation wired to the "Update FX" button. The hook
//     POSTs `/api/v1/fx/update/`, which refetches yfinance rates for every
//     property owned by the requester; on success it invalidates `fx.all`,
//     `transactions.all` (FX-derived amounts are stale).
//
// The page is read-only — the spec does not call for create/edit/delete on
// FX rates (they're system-derived), so the only mutation affordance is the
// "Update FX" refresh button in the header.
import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { useFX, useUpdateFX } from '@/api/fx'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDate } from '@/lib/format'
import type { FX } from '@/types/fx'

// One row per currency pair: the most recent snapshot for that pair plus
// the inverse rate (1 / rate) for at-a-glance conversion in both directions.
// `id` is a synthetic 1-based index so the row has a stable React key.
type LatestRate = {
  id: number
  pair: string
  from_currency: string
  to_currency: string
  rate: string
  date: string
  inverse: string
}

// Collapse the raw FX history to the latest snapshot per currency pair,
// optionally restricted to snapshots observed at or before `asOf`
// (ISO `YYYY-MM-DD`). Dates are ISO `YYYY-MM-DD` strings, so lexicographic
// comparison matches chronological order — no Date parsing needed.
function latestRatePerPair(rows: FX[], asOf?: string): LatestRate[] {
  const latest = new Map<string, FX>()
  for (const row of rows) {
    if (asOf && row.date > asOf) continue
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

  // Task 11: optional "as of" date. Empty string means "latest available".
  // Controlled input lets the user pick a past date to see historical
  // latest-per-pair rates; clearing the input reverts to today's view.
  const [asOf, setAsOf] = useState('')

  const summary = useMemo(
    () => (data ? latestRatePerPair(data, asOf || undefined) : []),
    [data, asOf],
  )

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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">FX Rates</h1>
          <p className="text-sm text-muted-foreground">
            {asOf
              ? `Latest rate per currency pair as of ${formatDate(asOf)} (${summary.length} ${
                  summary.length === 1 ? 'pair' : 'pairs'
                }).`
              : `Latest rate per currency pair (${summary.length} ${
                  summary.length === 1 ? 'pair' : 'pairs'
                }).`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Date scope: filters the history to rates observed at or
              before the chosen date, then takes the latest per pair.
              Native <input type="date"> is enough — no need for a full
              calendar popover for a single-date picker. */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <label htmlFor="fx-as-of" className="whitespace-nowrap">
              As of
            </label>
            <Input
              id="fx-as-of"
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="h-8 w-[150px]"
            />
            {asOf && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setAsOf('')}
              >
                Clear
              </Button>
            )}
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
      </div>

      {/* Plain <Table> instead of DataTable so there are no pagination
          controls — the summary is short (one row per pair) and the spec
          asks for pagination to be removed. */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Pair</TableHead>
              <TableHead>Rate</TableHead>
              <TableHead>Inverse</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summary.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="text-sm text-muted-foreground"
                >
                  No rates on or before {formatDate(asOf)}.
                </TableCell>
              </TableRow>
            ) : (
              summary.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <span className="font-medium">
                      {row.from_currency} → {row.to_currency}
                    </span>
                  </TableCell>
                  <TableCell>
                    {/* The serializer returns the rate as a stringified
                        decimal; display it verbatim (no rounding) so users
                        see exactly what the backend stored. The rate lives
                        in its own <span> so screen readers and tests can
                        target the numeric value directly. */}
                    <span className="font-mono">
                      1 {row.from_currency} ={' '}
                      <span data-testid="rate-value">{row.rate}</span>{' '}
                      {row.to_currency}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="font-mono text-muted-foreground">
                      1 {row.to_currency} = {row.inverse}{' '}
                      {row.from_currency}
                    </span>
                  </TableCell>
                  <TableCell>{formatDate(row.date)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
