// frontend/src/pages/PropertiesPage.tsx
//
// Properties list page (Task 2 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `usePropertiesWithStats` for the table rows (joined with Transaction
//     aggregates so we can show net income columns).
//   - `useCreateProperty` / `useDeleteProperty` mutations, wired into the
//     `EntityFormDialog` (create) and `ConfirmDialog` (delete) modals.
//
// Layout (per the user's redesign request):
//   - Two-row table header: super-header "All time" + "YTD" each spanning
//     the Revenue / Expenses / Net sub-columns; "Property / Location /
//     Currency" sit alone on the left, in a rowSpan=2 cell.
//   - Stats values are FX-converted to USD on the backend (exposed as
//     `stats_currency`); each value is rendered with `$` (the actual
//     currency the number is in). A small note below the table reminds the
//     user that the stats columns are USD-converted — the native currency
//     column shows RUB/GBP for context.
//
// Adaptation note vs the original task-2 brief: the B1 review established
// that `EntityFormDialog` uses `title` + `children` (ReactNode), not the
// `entity` / `onSuccess` / render-prop signature the brief assumed. We pass
// `<PropertyForm>` directly as the dialog body and wire the mutation inside
// the form's `onSubmit`. Likewise `EmptyState` takes `actionLabel` +
// `onAction`, not an `action` element. We also surface a row-level delete
// button (the brief's ConfirmDialog wiring referenced a `deleteTarget`
// state but no UI set it; an actions column closes that loop honestly).
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  useCreateProperty,
  useDeleteProperty,
  usePropertiesWithStats,
} from '@/api/properties'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { PropertyForm } from '@/components/forms/PropertyForm'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatCurrency } from '@/lib/format'
import type { PropertyWithStats } from '@/types/property'

export function PropertiesPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = usePropertiesWithStats()
  const createProperty = useCreateProperty()
  const deleteProperty = useDeleteProperty()

  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<PropertyWithStats | null>(
    null,
  )

  if (isLoading) {
    return <SkeletonTable />
  }

  if (isError) {
    return (
      <ErrorState
        message="Failed to load properties"
        onRetry={() => refetch()}
      />
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="No properties yet"
          description="Create your first property to start tracking."
          actionLabel="New Property"
          onAction={() => setCreateOpen(true)}
        />
        <EntityFormDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          title="Property"
          mode="create"
        >
          <PropertyForm
            onSubmit={(values) =>
              createProperty.mutate(values, {
                onSuccess: () => {
                  toast.success('Property created')
                  setCreateOpen(false)
                },
                onError: () => toast.error('Failed to create property'),
              })
            }
            isSubmitting={createProperty.isPending}
          />
        </EntityFormDialog>
      </div>
    )
  }

  // Stats come back FX-converted to a single target currency (USD by
  // default); the backend exposes this as `stats_currency`. Every property
  // shares the same stats currency in the response (one request, one
  // target), so we can pull it from the first row.
  const statsCurrency = data[0]?.stats_currency ?? 'USD'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Properties</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Property
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {/* Super-header row: spans the Revenue/Expenses/Net triplets. */}
            <TableRow>
              <TableHead rowSpan={2}>Property</TableHead>
              <TableHead rowSpan={2}>Location</TableHead>
              <TableHead rowSpan={2}>Currency</TableHead>
              <TableHead colSpan={3} className="text-center border-l">
                All time
              </TableHead>
              <TableHead colSpan={3} className="text-center border-l">
                YTD
              </TableHead>
              <TableHead rowSpan={2} />
            </TableRow>
            {/* Sub-header row: Revenue / Expenses / Net under each
                super-header. */}
            <TableRow>
              <TableHead className="text-right border-l">Revenue</TableHead>
              <TableHead className="text-right">Expenses</TableHead>
              <TableHead className="text-right">Net</TableHead>
              <TableHead className="text-right border-l">Revenue</TableHead>
              <TableHead className="text-right">Expenses</TableHead>
              <TableHead className="text-right">Net</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow
                key={row.id}
                onClick={() => navigate(`/properties/${row.id}`)}
                className="cursor-pointer"
              >
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell>{row.location}</TableCell>
                <TableCell>{row.currency || '—'}</TableCell>
                <TableCell className="text-right border-l">
                  {formatCurrency(row.gross_income_all_time, statsCurrency)}
                </TableCell>
                <TableCell className="text-right">
                  {/* Expenses come back as negative numbers from the
                      backend; show the absolute value (the P&L table
                      presents expenses as positive magnitudes). */}
                  {formatCurrency(
                    Math.abs(row.expenses_all_time),
                    statsCurrency,
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(row.net_income_all_time, statsCurrency)}
                </TableCell>
                <TableCell className="text-right border-l">
                  {formatCurrency(row.gross_income_ytd, statsCurrency)}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(Math.abs(row.expenses_ytd), statsCurrency)}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(row.net_income_ytd, statsCurrency)}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Delete ${row.name}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeleteTarget(row)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        Revenue / Expenses / Net columns are FX-converted to {statsCurrency}{' '}
        on the backend. The Currency column shows each property's native
        currency.
      </p>

      <EntityFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Property"
        mode="create"
      >
        <PropertyForm
          onSubmit={(values) =>
            createProperty.mutate(values, {
              onSuccess: () => {
                toast.success('Property created')
                setCreateOpen(false)
              },
              onError: () => toast.error('Failed to create property'),
            })
          }
          isSubmitting={createProperty.isPending}
        />
      </EntityFormDialog>

      {deleteTarget && (
        <ConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null)
          }}
          title={`Delete ${deleteTarget.name}?`}
          description="This action cannot be undone."
          confirmText="Delete"
          confirmVariant="destructive"
          isLoading={deleteProperty.isPending}
          onConfirm={() => {
            if (!deleteTarget) return
            deleteProperty.mutate(deleteTarget.id, {
              onSuccess: () => {
                toast.success('Property deleted')
                setDeleteTarget(null)
              },
              onError: () => toast.error('Failed to delete property'),
            })
          }}
        />
      )}
    </div>
  )
}
