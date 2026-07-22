// frontend/src/pages/PropertiesPage.tsx
//
// Properties list page (Task 2 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `usePropertiesWithStats` for the table rows (joined with Transaction
//     aggregates so we can show net income columns).
//   - `useCreateProperty` mutation wired into the `EntityFormDialog`.
//
// Layout (per the user's redesign request):
//   - Two-row table header: super-header "All time" + "YTD" each spanning
//     the Revenue / Expenses / Net sub-columns; "Property / Location /
//     Currency" sit alone on the left, in a rowSpan=2 cell, bottom-aligned.
//   - Stats values are shown in each property's NATIVE currency (the
//     backend returns native-currency figures when no `currency` query
//     param is supplied — see `views.PropertyViewSet.with_stats`). A
//     small note below the table reminds the user of this.
//
// Adaptation note vs the original task-2 brief: the B1 review established
// that `EntityFormDialog` uses `title` + `children` (ReactNode), not the
// `entity` / `onSuccess` / render-prop signature the brief assumed. We pass
// `<PropertyForm>` directly as the dialog body and wire the mutation inside
// the form's `onSubmit`. Likewise `EmptyState` takes `actionLabel` +
// `onAction`, not an `action` element. The row-level delete button has been
// removed per the user's request — row click navigates to the detail page,
// where Edit / Delete affordances live.
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'

import {
  useCreateProperty,
  usePropertiesWithStats,
} from '@/api/properties'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
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

export function PropertiesPage() {
  const navigate = useNavigate()
  // No `currency` arg => backend returns per-property NATIVE-currency
  // aggregates (no FX conversion). The native currency lives on each
  // row's `currency` field; the stats values are already in that currency.
  const { data, isLoading, isError, refetch } = usePropertiesWithStats()
  const createProperty = useCreateProperty()

  const [createOpen, setCreateOpen] = useState(false)

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

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {/* Super-header row: spans the Revenue/Expenses/Net triplets.
                The first three columns (Property / Location / Currency)
                are rowSpan=2 so they vertically span both header rows;
                `align-bottom` pins their text to the bottom (sitting on
                the same baseline as the Revenue/Expenses/Net sub-header
                row) so the visual hierarchy reads cleanly. */}
            <TableRow>
              <TableHead rowSpan={2} className="align-bottom">Property</TableHead>
              <TableHead rowSpan={2} className="align-bottom">Location</TableHead>
              <TableHead rowSpan={2} className="align-bottom">Currency</TableHead>
              <TableHead colSpan={3} className="text-center border-l">
                All time
              </TableHead>
              <TableHead colSpan={3} className="text-center border-l">
                YTD
              </TableHead>
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
                  {formatCurrency(row.gross_income_all_time, row.currency)}
                </TableCell>
                <TableCell className="text-right">
                  {/* Expenses come back as negative numbers from the
                      backend; show the absolute value (the P&L table
                      presents expenses as positive magnitudes). */}
                  {formatCurrency(
                    Math.abs(row.expenses_all_time),
                    row.currency,
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(row.net_income_all_time, row.currency)}
                </TableCell>
                <TableCell className="text-right border-l">
                  {formatCurrency(row.gross_income_ytd, row.currency)}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(Math.abs(row.expenses_ytd), row.currency)}
                </TableCell>
                <TableCell className="text-right">
                  {formatCurrency(row.net_income_ytd, row.currency)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-xs text-muted-foreground">
        Revenue / Expenses / Net columns are shown in each property's native
        currency (no FX conversion).
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
    </div>
  )
}
