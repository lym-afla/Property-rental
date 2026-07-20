// frontend/src/pages/PropertiesPage.tsx
//
// Properties list page (Task 2 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `usePropertiesWithStats` for the table rows (joined with Transaction
//     aggregates so we can show net income columns).
//   - `useCreateProperty` / `useDeleteProperty` mutations, wired into the
//     `EntityFormDialog` (create) and `ConfirmDialog` (delete) modals.
//   - `DataTable`, `SkeletonTable`, `EmptyState`, `ErrorState` for the
//     loading / empty / error / data affordances.
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
import { type ColumnDef } from '@tanstack/react-table'
import { Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  useCreateProperty,
  useDeleteProperty,
  usePropertiesWithStats,
} from '@/api/properties'
import { DataTable } from '@/components/table/DataTable'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { PropertyForm } from '@/components/forms/PropertyForm'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
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

  // The columns are built inside the component so the row delete handler can
  // close over `setDeleteTarget`. `DataTable` is generic over the row shape;
  // passing a fresh array on each render is cheap (TanStack memoizes the
  // table model internally).
  const columns: ColumnDef<PropertyWithStats>[] = [
    { accessorKey: 'name', header: 'Property' },
    { accessorKey: 'location', header: 'Location' },
    {
      accessorKey: 'net_income_all_time',
      header: 'Net (All-time)',
      cell: ({ row }) =>
        formatCurrency(
          row.original.net_income_all_time,
          row.original.currency,
        ),
    },
    {
      accessorKey: 'net_income_ytd',
      header: 'Net (YTD)',
      cell: ({ row }) =>
        formatCurrency(row.original.net_income_ytd, row.original.currency),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Delete ${row.original.name}`}
          // Stop propagation so the row's onClick (navigate to detail) does
          // not fire alongside the delete intent.
          onClick={(e) => {
            e.stopPropagation()
            setDeleteTarget(row.original)
          }}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      ),
    },
  ]

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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Properties</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Property
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={data}
        onRowClick={(row) => navigate(`/properties/${row.id}`)}
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
