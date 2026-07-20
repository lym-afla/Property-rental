// frontend/src/pages/TenantDetailPage.tsx
//
// Tenant detail page (Task 5 of Plan B2).
//
// Layout:
//   - Header card: tenant name + property name + lease dates + rent rate
//     + debt + status badge, with Edit / Vacate actions for the tenant.
//   - Tabs (shadcn):
//       * "Overview" — recent transactions subset for this tenant
//         (`?tenant=<id>` filter), plus a debt summary panel with a chart
//         placeholder reserved for Plan C.
//       * "Lease timeline" — a chronological list of lease events derived
//         from the tenant's own fields (lease_start, lease_end) and the
//         rent-category transactions (each rent payment is functionally
//         a "lease rent applied" event). Plan B1 does not expose a
//         dedicated `Lease_rent` history endpoint, so we derive the
//         timeline client-side from the data we already have; the slot
//         is structured so a future `useLeaseRentHistory(id)` hook can
//         replace the derived rows without touching the page layout.
//
// Chart placeholder: the Overview tab reserves a card slot for an
// upcoming chart (filled by Plan C). Until then it renders a commented
// placeholder so the layout doesn't shift when the chart lands.
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
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { ArrowLeft, Pencil, LogOut } from 'lucide-react'
import { toast } from 'sonner'

import {
  useTenant,
  useTenantsWithStats,
  useUpdateTenant,
} from '@/api/tenants'
import { useProperty } from '@/api/properties'
import { useTransactions } from '@/api/transactions'
import { DataTable } from '@/components/table/DataTable'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { VacateTenantDialog } from '@/components/modals/VacateTenantDialog'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatCurrency, formatDate } from '@/lib/format'
import type { TenantWithStats } from '@/types/tenant'
import type { Transaction } from '@/types/transaction'

// Number of recent transactions shown in the Overview tab. The full list
// lives on the Transactions page; the detail page only surfaces a taste
// so the debt/rent panel has supporting context.
const RECENT_TRANSACTIONS_PREVIEW = 5

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

// One row in the lease timeline. `kind` discriminates the event source;
// `date` is the canonical sort key (ISO `YYYY-MM-DD`).
type LeaseEvent = {
  date: string
  label: string
  detail?: string
  kind: 'lease-start' | 'lease-end' | 'rent-payment'
}

export function TenantDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const tenantId = Number(id)

  const tenantQuery = useTenant(tenantId)
  const statsQuery = useTenantsWithStats()
  const transactionsQuery = useTransactions({ tenant: tenantId })
  const updateTenant = useUpdateTenant()

  const [editOpen, setEditOpen] = useState(false)
  const [vacateOpen, setVacateOpen] = useState(false)

  const tenant = tenantQuery.data

  // Pick the matching stats row from the with_stats list. `find` is O(n)
  // but tenant counts are small; the React Query cache absorbs repeat
  // navigations back to the list page.
  const stats: TenantWithStats | undefined = useMemo(() => {
    return statsQuery.data?.find((t) => t.id === tenantId)
  }, [statsQuery.data, tenantId])

  // The property FK is on the tenant; once the tenant loads we can fetch
  // the property for its name + currency. `useProperty(NaN)` would 404
  // and surface an error state, so we only fire it once we have a real id.
  const propertyId = tenant?.property
  const propertyQuery = useProperty(
    Number.isFinite(propertyId) && propertyId ? propertyId : 0,
  )
  const property = propertyQuery.data
  const currency = property?.currency ?? ''

  // Build a lease timeline: lease_start, every rent payment, lease_end.
  // Most-recent-first so the most actionable events (upcoming vacate,
  // latest payment) sit at the top.
  const leaseEvents = useMemo<LeaseEvent[]>(() => {
    const events: LeaseEvent[] = []
    if (tenant?.lease_start) {
      events.push({
        date: tenant.lease_start,
        label: 'Lease started',
        detail: `Payday: day ${tenant.payday} of the month`,
        kind: 'lease-start',
      })
    }
    for (const t of transactionsQuery.data ?? []) {
      if (t.category !== 'rent') continue
      events.push({
        date: t.date,
        label: 'Rent payment',
        detail: `${formatCurrency(Number(t.amount), t.currency)}${
          t.comment ? ` — ${t.comment}` : ''
        }`,
        kind: 'rent-payment',
      })
    }
    if (tenant?.lease_end) {
      events.push({
        date: tenant.lease_end,
        label: 'Lease ends',
        detail: 'Tenant marked as vacating as of this date.',
        kind: 'lease-end',
      })
    }
    events.sort((a, b) => b.date.localeCompare(a.date))
    return events
  }, [tenant, transactionsQuery.data, currency])

  const recentTransactions = useMemo(() => {
    const txns = [...(transactionsQuery.data ?? [])]
    txns.sort((a, b) => b.date.localeCompare(a.date))
    return txns.slice(0, RECENT_TRANSACTIONS_PREVIEW)
  }, [transactionsQuery.data])

  const transactionColumns: ColumnDef<Transaction>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => formatDate(row.original.date),
    },
    { accessorKey: 'category', header: 'Category' },
    {
      accessorKey: 'type',
      header: 'Type',
      cell: ({ row }) => (
        <Badge
          variant={row.original.type === 'income' ? 'secondary' : 'outline'}
          className="capitalize"
        >
          {row.original.type}
        </Badge>
      ),
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ row }) =>
        formatCurrency(Number(row.original.amount), row.original.currency),
    },
  ]

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
                    stats && stats.debt > 0
                      ? 'font-medium text-destructive'
                      : ''
                  }
                >
                  {stats ? formatCurrency(stats.debt, currency) : '—'}
                </span>
              }
            />
          </dl>
        </CardContent>
      </Card>

      {/* Tabs -------------------------------------------------------------- */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="timeline">Lease timeline</TabsTrigger>
        </TabsList>

        {/* Overview tab -------------------------------------------------- */}
        <TabsContent value="overview" className="space-y-6 pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Rent &amp; debt</CardTitle>
              <CardDescription>
                Lifetime revenue and outstanding debt for this tenant.
                Currency shown in {currency || '—'}.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Chart placeholder — Plan C will mount the revenue/debt
                  chart here. Keeping the slot visible (vs. omitting it)
                  means the tab layout won't reflow when the chart lands. */}
              {/* <RevenueChart tenant={tenant} currency={currency} /> */}
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Stat
                  label="Revenue (all-time)"
                  value={
                    stats
                      ? formatCurrency(stats.revenue_all_time, currency)
                      : '—'
                  }
                />
                <Stat
                  label="Revenue (YTD)"
                  value={
                    stats
                      ? formatCurrency(stats.revenue_ytd, currency)
                      : '—'
                  }
                />
                <Stat
                  label="Debt"
                  value={
                    stats ? (
                      <span
                        className={
                          stats.debt > 0
                            ? 'font-medium text-destructive'
                            : ''
                        }
                      >
                        {formatCurrency(stats.debt, currency)}
                      </span>
                    ) : (
                      '—'
                    )
                  }
                />
              </dl>
            </CardContent>
          </Card>

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
              <DataTable
                columns={transactionColumns}
                data={recentTransactions}
              />
            )}
          </div>
        </TabsContent>

        {/* Lease timeline tab -------------------------------------------- */}
        <TabsContent value="timeline" className="space-y-4 pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Lease timeline</CardTitle>
              <CardDescription>
                Lease milestones and rent payments in reverse-chronological
                order.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {leaseEvents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No lease events recorded yet.
                </p>
              ) : (
                <ol className="space-y-3">
                  {leaseEvents.map((evt, idx) => (
                    <li
                      key={`${evt.kind}-${evt.date}-${idx}`}
                      className="flex flex-col gap-1 border-l-2 border-muted pl-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {evt.label}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(evt.date)}
                        </span>
                      </div>
                      {evt.detail ? (
                        <span className="text-sm text-muted-foreground">
                          {evt.detail}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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
