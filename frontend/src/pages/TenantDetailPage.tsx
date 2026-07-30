// frontend/src/pages/TenantDetailPage.tsx
//
// Tenant detail page (Task 5 of Plan B2).
//
// Layout:
//   - Header card: tenant name + property name + lease dates + rent rate
//     + debt + status badge, with Edit / Update rent / Vacate actions.
//   - Overview section: server-provided rent and debt statistics, typed
//     rent-performance analytics, and the 5 most-recent transactions for
//     THIS tenant (filtered server-side via `?tenant=<id>`).
//
// Charts: the Overview section mounts RentPerformanceChart with the
// server-provided expected, received, variance, and arrears series.
//
// B1 adaptation notes (vs the original task-5 brief):
//   - `useTenant(id)` returns the plain `Tenant` shape, but the header
//     needs the tenant's `rent_rate` and `debt`. Rather than fetch the
//     whole `with_stats` list and find one row, we use
//     `useTenantsWithStats()` and pick the matching id — it's the same
//     request the list page already caches, so React Query dedupes.
//   - Property name + currency come from `useProperty(tenant.property)`.
//     The page reuses the same hook the property detail page uses, so
//     the cache is shared across pages.
//   - Transactions come from `useTransactions({ tenant: id })` — the
//     filter is applied server-side by the ViewSet.
//   - "Update rent" POSTs a new `Lease_rent` entry via
//     `/api/v1/lease-rents/` (see `UpdateRentDialog`); the mutation
//     invalidates the tenants cache so `rent_rate` refetches.
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, LogOut } from 'lucide-react'
import { toast } from 'sonner'

import {
  useTenant,
  useTenantsWithStats,
  useUpdateTenant,
} from '@/api/tenants'
import { useProperty } from '@/api/properties'
import { useTransactions } from '@/api/transactions'
import { useTenantRentPerformance } from '@/api/analytics'
import { useSession } from '@/context/SessionProvider'
import { RentPerformanceChart } from '@/features/tenant/RentPerformanceChart'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { VacateTenantDialog } from '@/components/modals/VacateTenantDialog'
import { UpdateRentDialog } from '@/components/modals/UpdateRentDialog'
import { TenantForm } from '@/components/forms/TenantForm'
import { ErrorState } from '@/components/states/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatAccounting, formatCurrency, formatDate } from '@/lib/format'
import { transactionCategoryLabel } from '@/lib/transactionCategories'
import type { TenantWithStats } from '@/types/tenant'

// Number of recent transactions shown in the Overview tab. The full list
// lives on the Transactions page; the detail page surfaces only the most
// recent activity (no pagination controls).
const RECENT_TRANSACTIONS_LIMIT = 5

// Status bucketing — same rules as TenantsPage; duplicated because the
// list page and detail page are independent and we don't want a shared
// utils module for one tiny function. If a third caller appears, extract.
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

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { user } = useSession()

  const tenantId = Number(id)

  const tenantQuery = useTenant(tenantId)
  // Resolve the tenant's property so we can read its native currency for
  // display. We THEN fetch `with_stats` WITHOUT a currency arg — the
  // backend returns per-tenant NATIVE-currency figures (no FX
  // conversion), which is what the card + recent-transactions table
  // need. Stats currency equals the tenant's property currency.
  const propertyIdFromTenant = tenantQuery.data?.property
  const propertyPreview = useProperty(
    Number.isFinite(propertyIdFromTenant) && propertyIdFromTenant
      ? propertyIdFromTenant
      : 0,
  )
  const transactionsQuery = useTransactions({ tenant: tenantId })
  const statsQuery = useTenantsWithStats()
  const updateTenant = useUpdateTenant()

  // Use server-provided expected, received, variance, and arrears values.
  // The start is the lease start once available; no React-side financial
  // calculation is used by the chart.
  const rentPerformanceQuery = useTenantRentPerformance(tenantId, {
    start: tenantQuery.data?.lease_start ?? user?.effective_date ?? undefined,
    end: user?.effective_date ?? undefined,
    grain: 'month',
  })

  const [editOpen, setEditOpen] = useState(false)
  const [vacateOpen, setVacateOpen] = useState(false)
  const [updateRentOpen, setUpdateRentOpen] = useState(false)

  const tenant = tenantQuery.data

  // Pick the matching stats row from the with_stats list. `find` is O(n)
  // but tenant counts are small; the React Query cache absorbs repeat
  // navigations back to the list page.
  const stats: TenantWithStats | undefined = useMemo(() => {
    return statsQuery.data?.find((t) => t.id === tenantId)
  }, [statsQuery.data, tenantId])

  // Reuse the property we already fetched up top (for the native
  // currency) — there's no point firing a second `useProperty` request
  // for the same id. `property` here is the same record as
  // `propertyPreview.data`.
  const property = propertyPreview.data
  const currency = property?.currency ?? ''

  const recentTransactions = useMemo(() => {
    const txns = [...(transactionsQuery.data ?? [])]
    txns.sort((a, b) => b.date.localeCompare(a.date))
    return txns.slice(0, RECENT_TRANSACTIONS_LIMIT)
  }, [transactionsQuery.data])

  // ---- Render guards -------------------------------------------------------

  if (tenantQuery.isLoading) {
    return <TenantDetailSkeleton />
  }

  if (tenantQuery.isError || !tenant) {
    return (
      <div className="space-y-4">
        <BackButton onClick={() => navigate('/tenants')} />
        <ErrorState
          message="Failed to load tenant"
          onRetry={() => tenantQuery.refetch()}
        />
      </div>
    )
  }

  const status = tenantStatus(tenant.lease_end)
  const fullName = `${tenant.first_name} ${tenant.last_name}`

  // ---- Main render ---------------------------------------------------------

  return (
    <div className="space-y-6">
      <BackButton onClick={() => navigate('/tenants')} />

      {/* Header card ------------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{fullName}</CardTitle>
          <CardDescription>
            {property ? property.name : `Property #${tenant.property}`}
            {' · '}
            <Badge variant={STATUS_VARIANT[status]}>
              {STATUS_LABEL[status]}
            </Badge>
          </CardDescription>
          <CardAction>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditOpen(true)}
              >
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
              {/* Update rent — Task 24. Opens `UpdateRentDialog`, which
                  POSTs a new `Lease_rent` entry (effective date +
                  amount) via `/api/v1/lease-rents/`. The mutation
                  invalidates `tenants.all` so the cached `rent_rate`
                  refetches with the new rate. */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUpdateRentOpen(true)}
              >
                Update rent
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setVacateOpen(true)}
                // A vacated tenant can't be re-vacated; disable so the
                // affordance matches reality. (Editing lease_end directly
                // is the recovery path if a date was wrong.)
                disabled={status === 'vacated'}
              >
                <LogOut className="h-4 w-4" />
                Vacate
              </Button>
            </div>
          </CardAction>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <Stat
              label="Lease start"
              value={formatDate(tenant.lease_start)}
            />
            <Stat
              label="Lease end"
              value={tenant.lease_end ? formatDate(tenant.lease_end) : 'Open'}
            />
            <Stat
              label="Rent rate"
              value={
                stats
                  ? formatCurrency(Number(stats.rent_rate), currency)
                  : '—'
              }
            />
            <Stat
              label="Debt"
              value={
                <span
                  className={
                    stats
                      ? stats.debt > 0
                        ? 'font-medium text-emerald-600'
                        : stats.debt < 0
                          ? 'font-medium text-destructive'
                          : ''
                      : ''
                  }
                >
                  {stats ? formatAccounting(stats.debt, currency) : '—'}
                </span>
              }
            />
          </dl>
        </CardContent>
      </Card>

      {/* Overview section -------------------------------------------------- */}
      <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Rent &amp; debt</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat
                  label="Revenue (all-time)"
                  value={
                    stats
                      ? formatAccounting(stats.revenue_all_time, currency)
                      : '—'
                  }
                />
                <Stat
                  label="Revenue (YTD)"
                  value={
                    stats
                      ? formatAccounting(stats.revenue_ytd, currency)
                      : '—'
                  }
                />
                <Stat
                  label="Current rent"
                  value={stats ? formatAccounting(stats.rent_rate, currency) : '—'}
                />
                <Stat
                  label="Outstanding debt"
                  value={stats ? formatAccounting(stats.debt, currency) : '—'}
                />
              </dl>
            </CardContent>
          </Card>

          <RentPerformanceChart
            data={rentPerformanceQuery.data}
            isLoading={rentPerformanceQuery.isLoading}
            isError={rentPerformanceQuery.isError}
            onRetry={() => rentPerformanceQuery.refetch()}
          />

          <div className="space-y-2">
            <h2 className="text-lg font-semibold">Recent transactions</h2>
            {transactionsQuery.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : transactionsQuery.isError ? (
              <ErrorState
                message="Failed to load transactions"
                onRetry={() => transactionsQuery.refetch()}
              />
            ) : recentTransactions.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No transactions for this tenant yet.
              </p>
            ) : (
              /* The list is already filtered to THIS tenant via
                 `useTransactions({ tenant: id })` (the ViewSet applies
                 the `?tenant=<id>` filter server-side); pagination is
                 removed and the list is sliced client-side to the last
                 `RECENT_TRANSACTIONS_LIMIT` (5) — the full list lives on
                 the Transactions page. */
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recentTransactions.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell>{formatDate(t.date)}</TableCell>
                        <TableCell>{transactionCategoryLabel(t.category)}</TableCell>
                        <TableCell>
                          <Badge
                            variant={t.type === 'income' ? 'secondary' : 'outline'}
                            className="capitalize"
                          >
                            {t.type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {formatAccounting(t.amount, t.currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </div>

      {/* ---- Dialogs ------------------------------------------------------ */}

      {/* Edit tenant */}
      <EntityFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        title="Tenant"
        mode="edit"
      >
        <TenantForm
          // Properties list is needed for the property Select. We have
          // `property` already loaded (the tenant's current property); if
          // the user wants to reassign the tenant we still need the full
          // list. We use the single property we know about as a fallback
          // so the Select always shows the current value; the edit form
          // is primarily for contact details + lease dates anyway.
          properties={property ? [property] : []}
          defaultValues={{
            first_name: tenant.first_name,
            last_name: tenant.last_name,
            phone: tenant.phone,
            email: tenant.email,
            lease_start: tenant.lease_start,
            lease_end: tenant.lease_end,
            payday: tenant.payday,
            property: tenant.property,
          }}
          onSubmit={(values) =>
            updateTenant.mutate(
              { id: tenant.id, data: values },
              {
                onSuccess: () => {
                  toast.success('Tenant updated')
                  setEditOpen(false)
                },
                onError: () => toast.error('Failed to update tenant'),
              },
            )
          }
          isSubmitting={updateTenant.isPending}
        />
      </EntityFormDialog>

      {/* Vacate tenant */}
      <VacateTenantDialog
        open={vacateOpen}
        onOpenChange={setVacateOpen}
        tenantId={tenant.id}
        tenantLabel={fullName}
      />

      {/* Update rent rate — POSTs a new `Lease_rent` entry (effective
          date + amount + property currency) via `/api/v1/lease-rents/`.
          On success the mutation invalidates `tenants.all` so the
          header's `rent_rate` (sourced from `with_stats`) refetches. */}
      <UpdateRentDialog
        open={updateRentOpen}
        onOpenChange={setUpdateRentOpen}
        tenantId={tenant.id}
        currency={currency}
        defaultRent={
          stats && typeof stats.rent_rate === 'number'
            ? String(stats.rent_rate)
            : typeof stats?.rent_rate === 'string' &&
                /^-?\d+(\.\d+)?$/.test(stats.rent_rate)
              ? stats.rent_rate
              : undefined
        }
        tenantLabel={fullName}
        onSuccess={() => setUpdateRentOpen(false)}
      />
    </div>
  )
}

// ---- Helpers ---------------------------------------------------------------

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick}>
      <ArrowLeft className="h-4 w-4" />
      Back to tenants
    </Button>
  )
}

function Stat({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

function TenantDetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-40" />
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}
