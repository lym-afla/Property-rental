// frontend/src/pages/TenantsPage.tsx
//
// Tenants list page (Task 4 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `useTenantsWithStats` for the table rows (joined with Transaction
//     aggregates + the current `Lease_rent` so we can show rent rate /
//     revenue / debt columns).
//   - `useProperties` so we can map the tenant's `property` FK to the
//     property `name` (and currency) for display. `TenantSerializer` only
//     exposes the property id, not its name, so the lookup has to happen
//     client-side.
//   - `useCreateTenant` mutation wired into the `EntityFormDialog` (create)
//     via `TenantForm`, mirroring PropertiesPage.
//   - `VacateTenantDialog` for the per-row Vacate action.
//   - `DataTable`, `SkeletonTable`, `EmptyState`, `ErrorState` for the
//     loading / empty / error / data affordances.
//
// Status derivation (`Active` / `Vacated` / `Will vacate`):
//   - `lease_end` null  -> Active (open-ended lease)
//   - `lease_end` >= today -> Active now, but will vacate; we tag
//     "Will vacate" so landlords can see upcoming churn.
//   - `lease_end` < today -> Vacated.
//
// B1 adaptation notes (vs the original task-4 brief):
//   - `EntityFormDialog` takes `title` + `children` (the form), not a
//     render-prop — we wire the mutation inside `TenantForm.onSubmit` and
//     close the dialog on success, mirroring PropertiesPage.
//   - `TenantForm` requires a `properties: Property[]` prop (the dropdown
//     of properties the tenant can be assigned to); we feed the same
//     `useProperties()` result we already use for the name lookup.
//   - `TenantWithStats.rent_rate` is typed as `number | string` because
//     the API serializes the decimal as a string in some code paths; we
//     coerce via `Number()` before formatting.
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Plus, LogOut } from 'lucide-react'
import { toast } from 'sonner'

import {
  useCreateTenant,
  useTenantsWithStats,
} from '@/api/tenants'
import { useProperties } from '@/api/properties'
import { DataTable } from '@/components/table/DataTable'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { VacateTenantDialog } from '@/components/modals/VacateTenantDialog'
import { TenantForm } from '@/components/forms/TenantForm'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatDate } from '@/lib/format'
import type { TenantWithStats } from '@/types/tenant'
import type { Property } from '@/types/property'

// Status bucketing — see the file header for the rules. We treat
// `lease_end` as a date string `YYYY-MM-DD` (the serializer format); a
// plain lexical comparison against today's ISO date is correct for that
// representation and avoids timezone pitfalls.
type TenantStatus = 'active' | 'will-vacate' | 'vacated'

function tenantStatus(leaseEnd: string | null | undefined): TenantStatus {
  if (!leaseEnd) return 'active'
  const today = new Date().toISOString().slice(0, 10)
  if (leaseEnd < today) return 'vacated'
  return 'will-vacate'
}

const STATUS_LABEL: Record<TenantStatus, string> = {
  active: 'Active',
  'will-vacate': 'Will vacate',
  vacated: 'Vacated',
}

const STATUS_VARIANT: Record<
  TenantStatus,
  'default' | 'secondary' | 'outline'
> = {
  active: 'secondary',
  'will-vacate': 'default',
  vacated: 'outline',
}

export function TenantsPage() {
  const navigate = useNavigate()
  const { data, isLoading, isError, refetch } = useTenantsWithStats()
  const propertiesQuery = useProperties()
  const createTenant = useCreateTenant()

  const [createOpen, setCreateOpen] = useState(false)
  const [vacateTarget, setVacateTarget] = useState<TenantWithStats | null>(
    null,
  )

  // Build a `propertyId -> Property` map so each tenant row can look up its
  // property name + currency in O(1) without a per-row `useProperty` call
  // (which would fan out N requests and reorder the rows).
  const propertyById = useMemo(() => {
    const map = new Map<number, Property>()
    for (const p of propertiesQuery.data ?? []) {
      map.set(p.id, p)
    }
    return map
  }, [propertiesQuery.data])

  const columns: ColumnDef<TenantWithStats>[] = [
    {
      id: 'name',
      header: 'Tenant',
      // Display "First Last"; sorting by the underlying field is a
      // secondary concern (TanStack falls back to row order).
      cell: ({ row }) =>
        `${row.original.first_name} ${row.original.last_name}`,
    },
    {
      id: 'property',
      header: 'Property',
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        return property?.name ?? `#${row.original.property}`
      },
    },
    {
      id: 'currency',
      header: 'Currency',
      // Surface each tenant's property currency code so the rent /
      // revenue / debt columns have an explicit FX context. Falls back
      // to an em dash if the property lookup missed (e.g. race during
      // create).
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        return property?.currency ?? '—'
      },
    },
    {
      accessorKey: 'lease_start',
      header: 'Renting since',
      cell: ({ row }) => formatDate(row.original.lease_start),
    },
    {
      id: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = tenantStatus(row.original.lease_end)
        return (
          <Badge variant={STATUS_VARIANT[status]}>
            {STATUS_LABEL[status]}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'rent_rate',
      header: 'Rent rate',
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        return formatCurrency(
          Number(row.original.rent_rate),
          property?.currency ?? '',
        )
      },
    },
    {
      accessorKey: 'revenue_all_time',
      header: 'Revenue (all-time)',
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        return formatCurrency(
          row.original.revenue_all_time,
          property?.currency ?? '',
        )
      },
    },
    {
      accessorKey: 'revenue_ytd',
      header: 'Revenue (YTD)',
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        return formatCurrency(
          row.original.revenue_ytd,
          property?.currency ?? '',
        )
      },
    },
    {
      accessorKey: 'debt',
      header: 'Debt',
      cell: ({ row }) => {
        const property = propertyById.get(row.original.property)
        const debt = row.original.debt
        return (
          <span className={debt > 0 ? 'font-medium text-destructive' : ''}>
            {formatCurrency(debt, property?.currency ?? '')}
          </span>
        )
      },
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const status = tenantStatus(row.original.lease_end)
        // Once vacated, the Vacate action is a no-op; hide it so the
        // affordance matches reality.
        if (status === 'vacated') return null
        return (
          <Button
            variant="outline"
            size="sm"
            aria-label={`Vacate ${row.original.first_name} ${row.original.last_name}`}
            // Stop propagation so the row's onClick (navigate to detail)
            // does not fire alongside the vacate intent.
            onClick={(e) => {
              e.stopPropagation()
              setVacateTarget(row.original)
            }}
          >
            <LogOut className="h-4 w-4" />
            Vacate
          </Button>
        )
      },
    },
  ]

  if (isLoading) {
    return <SkeletonTable />
  }

  if (isError) {
    return (
      <ErrorState
        message="Failed to load tenants"
        onRetry={() => refetch()}
      />
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="space-y-4">
        <EmptyState
          title="No tenants yet"
          description="Add your first tenant to start tracking rent."
          actionLabel="New Tenant"
          onAction={() => setCreateOpen(true)}
        />
        <EntityFormDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          title="Tenant"
          mode="create"
        >
          <TenantForm
            properties={propertiesQuery.data ?? []}
            onSubmit={(values) =>
              createTenant.mutate(values, {
                onSuccess: () => {
                  toast.success('Tenant created')
                  setCreateOpen(false)
                },
                onError: () => toast.error('Failed to create tenant'),
              })
            }
            isSubmitting={createTenant.isPending}
          />
        </EntityFormDialog>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tenants</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Tenant
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={data}
        onRowClick={(row) => navigate(`/tenants/${row.id}`)}
      />

      <EntityFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Tenant"
        mode="create"
      >
        <TenantForm
          properties={propertiesQuery.data ?? []}
          onSubmit={(values) =>
            createTenant.mutate(values, {
              onSuccess: () => {
                toast.success('Tenant created')
                setCreateOpen(false)
              },
              onError: () => toast.error('Failed to create tenant'),
            })
          }
          isSubmitting={createTenant.isPending}
        />
      </EntityFormDialog>

      {vacateTarget && (
        <VacateTenantDialog
          open={!!vacateTarget}
          onOpenChange={(open) => {
            if (!open) setVacateTarget(null)
          }}
          tenantId={vacateTarget.id}
          tenantLabel={`${vacateTarget.first_name} ${vacateTarget.last_name}`}
          onSuccess={() => setVacateTarget(null)}
        />
      )}
    </div>
  )
}
