// frontend/src/pages/FXPage.tsx
//
// FX rates list page (Task 7 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `useFX()` for the table rows.
//   - `useUpdateFX()` mutation wired to the "Update FX" button. The hook
//     POSTs `/api/v1/fx/update/`, which refetches yfinance rates for every
//     property owned by the requester; on success it invalidates `fx.all`,
//     `transactions.all`, and `chartData.all` (FX-derived amounts are stale).
//   - `DataTable`, `SkeletonTable`, `EmptyState`, `ErrorState`.
//
// The table is read-only — the spec does not call for create/edit/delete on
// FX rates (they're system-derived), so the only mutation affordance is the
// "Update FX" refresh button in the header.
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

export function FXPage() {
  const { data, isLoading, isError, refetch } = useFX()
  const updateFX = useUpdateFX()

  const columns: ColumnDef<FX>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => formatDate(row.original.date),
    },
    { accessorKey: 'from_currency', header: 'From' },
    { accessorKey: 'to_currency', header: 'To' },
    {
      accessorKey: 'rate',
      header: 'Rate',
      // The serializer returns the rate as a stringified decimal; display
      // it verbatim (no rounding) so users see exactly what the backend
      // stored.
      cell: ({ row }) => row.original.rate,
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
        <h1 className="text-2xl font-bold">FX Rates</h1>
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

      <DataTable columns={columns} data={data} />
    </div>
  )
}
