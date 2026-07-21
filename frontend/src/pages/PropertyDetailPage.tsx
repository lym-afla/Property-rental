// frontend/src/pages/PropertyDetailPage.tsx
//
// Property detail page (Task 3 of Plan B2).
//
// Layout:
//   - Header card: name / location / currency + key stats (bedrooms, area,
//     sold status) with Edit / Delete actions for the property itself.
//   - Tabs (shadcn):
//       * "Overview" — P&L breakdown derived from this property's
//         transactions (income / expenses / net) plus a recent-transactions
//         subset rendered through `DataTable`.
//       * "Valuations" — full `Property_capital_structure` list for the
//         property via `DataTable`, with create / edit / delete wired
//         through `EntityFormDialog` + `ConfirmDialog`.
//
// Charts (Plan C): the Overview tab mounts RentYieldChart (rent / value
// per period); the Valuations tab mounts ValuationChart (Debt + Equity
// stacked with total-value line). Both pull from a single
// `useChartData({type: 'property', elementId: id})` round-trip.
//
// B1 adaptation notes (vs the original task-3 brief):
//   - `EntityFormDialog` takes `title` + `children` (the form), not a
//     render-prop — we wire mutations inside each form's `onSubmit` and
//     close the dialog on success, mirroring PropertiesPage.
//   - `useProperty(id)` returns the plain `Property` shape (no stats), so
//     the P&L numbers are computed client-side from `useTransactions({
//     property: id })`. This keeps the page self-contained and avoids a
//     second `usePropertiesWithStats()` round-trip just to find one row.
//   - `usePropertyValuations(propertyId)` already filters server-side via
//     `?property=<id>`, so no client-side filter is needed.
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { ArrowLeft, Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  useDeleteProperty,
  useProperty,
  useUpdateProperty,
} from '@/api/properties'
import {
  useCreatePropertyValuation,
  useDeletePropertyValuation,
  usePropertyValuations,
  useUpdatePropertyValuation,
} from '@/api/propertyValuations'
import { useTransactions } from '@/api/transactions'
import { useChartData } from '@/api/charts'
import { ValuationChart } from '@/components/charts/ValuationChart'
import { RentYieldChart } from '@/components/charts/RentYieldChart'
import { DataTable } from '@/components/table/DataTable'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { PropertyForm, CURRENCY_OPTIONS } from '@/components/forms/PropertyForm'
import { PropertyValuationForm } from '@/components/forms/PropertyValuationForm'
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
import type { PropertyValuation } from '@/types/propertyValuation'
import type { Transaction } from '@/types/transaction'

// Number of recent transactions shown in the Overview tab. The full list
// lives on the Transactions page (Task 4); the detail page only surfaces a
// taste so the P&L panel has supporting context.
const RECENT_TRANSACTIONS_PREVIEW = 5

export function PropertyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // `Number(undefined) = NaN` and `Number('abc') = NaN`; either way the
  // fetch below 404s and we render the error affordance. Keeping the hook
  // call unconditional satisfies the Rules of Hooks even for malformed URLs.
  const propertyId = Number(id)

  const propertyQuery = useProperty(propertyId)
  const valuationsQuery = usePropertyValuations(propertyId)
  const transactionsQuery = useTransactions({ property: propertyId })

  // Property-scoped chart data: feeds ValuationChart (Debt + Equity per
  // period) and RentYieldChart (rent / value). A single round-trip covers
  // both since the chart-data view already returns the union of series
  // the property branch builds (`Debt`, `Equity`, plus the rent category
  // from the homePage-style aggregation). We pull 5 years of history so
  // both charts have meaningful context for established properties.
  const todayStr = new Date().toISOString().slice(0, 10)
  const fiveYearsAgo = (() => {
    const d = new Date()
    d.setFullYear(d.getFullYear() - 5)
    return d.toISOString().slice(0, 10)
  })()
  const chartQuery = useChartData({
    type: 'property',
    elementId: propertyId,
    frequency: 'M',
    start: fiveYearsAgo,
    end: todayStr,
  })

  const updateProperty = useUpdateProperty()
  const deleteProperty = useDeleteProperty()
  const createValuation = useCreatePropertyValuation()
  const updateValuation = useUpdatePropertyValuation()
  const deleteValuation = useDeletePropertyValuation()

  const [editPropertyOpen, setEditPropertyOpen] = useState(false)
  const [deletePropertyOpen, setDeletePropertyOpen] = useState(false)
  const [createValuationOpen, setCreateValuationOpen] = useState(false)
  const [editValuationTarget, setEditValuationTarget] =
    useState<PropertyValuation | null>(null)
  const [deleteValuationTarget, setDeleteValuationTarget] =
    useState<PropertyValuation | null>(null)

  const property = propertyQuery.data

  // P&L breakdown computed client-side from the property's transactions.
  // `Transaction.amount` is a stringified decimal (positive = income,
  // negative = expense); we sum by sign so a mis-coded sign on an expense
  // doesn't silently inflate income.
  const pnl = useMemo(() => {
    const txns = transactionsQuery.data ?? []
    let income = 0
    let expenses = 0
    for (const t of txns) {
      const amount = Number(t.amount)
      if (!Number.isFinite(amount)) continue
      if (amount >= 0) income += amount
      else expenses += Math.abs(amount)
    }
    return { income, expenses, net: income - expenses }
  }, [transactionsQuery.data])

  // Most-recent first; the API may or may not pre-sort, so we sort here to
  // make the preview deterministic regardless of backend ordering.
  const recentTransactions = useMemo(() => {
    const txns = [...(transactionsQuery.data ?? [])]
    txns.sort((a, b) => b.date.localeCompare(a.date))
    return txns.slice(0, RECENT_TRANSACTIONS_PREVIEW)
  }, [transactionsQuery.data])

  // Valuation columns are built inline so the edit/delete handlers can
  // close over component state. `property` is set implicitly from the
  // route on create, and is preserved on edit by passing the existing row
  // back through the PATCH.
  const valuationColumns: ColumnDef<PropertyValuation>[] = [
    {
      accessorKey: 'capital_structure_date',
      header: 'Date',
      cell: ({ row }) =>
        formatDate(row.original.capital_structure_date),
    },
    {
      accessorKey: 'capital_structure_value',
      header: 'Value',
      cell: ({ row }) =>
        formatCurrency(
          Number(row.original.capital_structure_value),
          property?.currency ?? '',
        ),
    },
    {
      accessorKey: 'capital_structure_debt',
      header: 'Debt',
      cell: ({ row }) =>
        formatCurrency(
          Number(row.original.capital_structure_debt),
          property?.currency ?? '',
        ),
    },
    {
      // Equity = value - debt. Helpful at a glance; the serializer doesn't
      // expose it as a field, so derive it here for display only.
      id: 'equity',
      header: 'Equity',
      cell: ({ row }) => {
        const equity =
          Number(row.original.capital_structure_value) -
          Number(row.original.capital_structure_debt)
        return formatCurrency(equity, property?.currency ?? '')
      },
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Edit valuation ${row.original.id}`}
            onClick={(e) => {
              e.stopPropagation()
              setEditValuationTarget(row.original)
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete valuation ${row.original.id}`}
            onClick={(e) => {
              e.stopPropagation()
              setDeleteValuationTarget(row.original)
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ]

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

  if (propertyQuery.isLoading) {
    return <PropertyDetailSkeleton />
  }

  if (propertyQuery.isError || !property) {
    return (
      <div className="space-y-4">
        <BackButton onClick={() => navigate('/properties')} />
        <ErrorState
          message="Failed to load property"
          onRetry={() => propertyQuery.refetch()}
        />
      </div>
    )
  }

  // ---- Main render ---------------------------------------------------------

  return (
    <div className="space-y-6">
      <BackButton onClick={() => navigate('/properties')} />

      {/* Header card ------------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">{property.name}</CardTitle>
          <CardDescription>
            {property.location}
            {property.sold
              ? ` · Sold ${formatDate(property.sold)}`
              : ' · Active'}
          </CardDescription>
          <CardAction>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditPropertyOpen(true)}
              >
                <Pencil className="h-4 w-4" />
                Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeletePropertyOpen(true)}
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </Button>
            </div>
          </CardAction>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <Stat label="Currency" value={property.currency} />
            <Stat label="Bedrooms" value={String(property.num_bedrooms)} />
            <Stat
              label="Area"
              value={property.area ? `${property.area} m²` : '—'}
            />
            <Stat
              label="Status"
              value={property.sold ? 'Sold' : 'Active'}
            />
          </dl>
        </CardContent>
      </Card>

      {/* Tabs -------------------------------------------------------------- */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="valuations">Valuations</TabsTrigger>
        </TabsList>

        {/* Overview tab -------------------------------------------------- */}
        <TabsContent value="overview" className="space-y-6 pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Profit &amp; Loss</CardTitle>
              <CardDescription>
                Derived from this property's transactions. Currency shown in{' '}
                {property.currency}.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Stat
                  label="Gross income"
                  value={formatCurrency(pnl.income, property.currency)}
                />
                <Stat
                  label="Expenses"
                  value={formatCurrency(pnl.expenses, property.currency)}
                />
                <Stat
                  label="Net income"
                  value={formatCurrency(pnl.net, property.currency)}
                />
              </dl>
            </CardContent>
          </Card>

          {/* Rent yield chart (Plan C). Sits between the P&L card and the
              recent-transactions table so the yield trend is visible right
              after the summary numbers it derives from. The chart owns its
              own loading/error states via ChartCard; we pass the chart-data
              payload through and let the chart fetch its own valuations
              (RentYieldChart calls usePropertyValuations internally). */}
          <RentYieldChart
            data={chartQuery.data ?? { labels: [], datasets: [], currency: property.currency }}
            propertyId={propertyId}
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
                No transactions for this property yet.
              </p>
            ) : (
              <DataTable
                columns={transactionColumns}
                data={recentTransactions}
              />
            )}
          </div>
        </TabsContent>

        {/* Valuations tab ------------------------------------------------ */}
        <TabsContent value="valuations" className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Capital structure</h2>
            <Button onClick={() => setCreateValuationOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New Valuation
            </Button>
          </div>

          {valuationsQuery.isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : valuationsQuery.isError ? (
            <ErrorState
              message="Failed to load valuations"
              onRetry={() => valuationsQuery.refetch()}
            />
          ) : !valuationsQuery.data || valuationsQuery.data.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No valuations recorded yet.
            </p>
          ) : (
            <DataTable
              columns={valuationColumns}
              data={valuationsQuery.data}
            />
          )}

          {/* Valuation chart (Plan C). Sits under the capital-structure
              table so users can read the same numbers as a trend. The
              chart-data request feeds Debt + Equity series; the chart
              overlays the sum (total value) as a line. */}
          <ValuationChart
            data={chartQuery.data ?? { labels: [], datasets: [], currency: property.currency }}
          />
        </TabsContent>
      </Tabs>

      {/* ---- Dialogs ------------------------------------------------------ */}

      {/* Edit property */}
      <EntityFormDialog
        open={editPropertyOpen}
        onOpenChange={setEditPropertyOpen}
        title="Property"
        mode="edit"
      >
        <PropertyForm
          defaultValues={{
            name: property.name,
            location: property.location,
            address: property.address,
            num_bedrooms: property.num_bedrooms,
            area: property.area ?? '',
            // `Property.currency` is a plain string at the type layer; the
            // form's zod schema restricts it to the CURRENCY_OPTIONS union.
            // The backend guarantees one of those values, so the narrowing
            // cast is safe — and if a stray value did sneak through, zod
            // catches it on submit.
            currency: CURRENCY_OPTIONS.includes(
              property.currency as (typeof CURRENCY_OPTIONS)[number],
            )
              ? (property.currency as (typeof CURRENCY_OPTIONS)[number])
              : 'USD',
            sold: property.sold,
          }}
          onSubmit={(values) =>
            updateProperty.mutate(
              { id: property.id, data: values },
              {
                onSuccess: () => {
                  toast.success('Property updated')
                  setEditPropertyOpen(false)
                },
                onError: () => toast.error('Failed to update property'),
              },
            )
          }
          isSubmitting={updateProperty.isPending}
        />
      </EntityFormDialog>

      {/* Delete property */}
      <ConfirmDialog
        open={deletePropertyOpen}
        onOpenChange={setDeletePropertyOpen}
        title={`Delete ${property.name}?`}
        description="This action cannot be undone. All transactions and valuations for this property will remain on the ledger."
        confirmText="Delete"
        confirmVariant="destructive"
        isLoading={deleteProperty.isPending}
        onConfirm={() => {
          deleteProperty.mutate(property.id, {
            onSuccess: () => {
              toast.success('Property deleted')
              navigate('/properties')
            },
            onError: () => toast.error('Failed to delete property'),
          })
        }}
      />

      {/* Create valuation */}
      <EntityFormDialog
        open={createValuationOpen}
        onOpenChange={setCreateValuationOpen}
        title="Valuation"
        mode="create"
        description="Record a snapshot of the property's value and debt."
      >
        <PropertyValuationForm
          onSubmit={(values) =>
            createValuation.mutate(
              { ...values, property: property.id },
              {
                onSuccess: () => {
                  toast.success('Valuation created')
                  setCreateValuationOpen(false)
                },
                onError: () => toast.error('Failed to create valuation'),
              },
            )
          }
          isSubmitting={createValuation.isPending}
        />
      </EntityFormDialog>

      {/* Edit valuation */}
      {editValuationTarget && (
        <EntityFormDialog
          open={!!editValuationTarget}
          onOpenChange={(open) => {
            if (!open) setEditValuationTarget(null)
          }}
          title="Valuation"
          mode="edit"
        >
          <PropertyValuationForm
            defaultValues={{
              capital_structure_date:
                editValuationTarget.capital_structure_date,
              capital_structure_value:
                editValuationTarget.capital_structure_value,
              capital_structure_debt:
                editValuationTarget.capital_structure_debt,
            }}
            onSubmit={(values) =>
              updateValuation.mutate(
                { id: editValuationTarget.id, data: values },
                {
                  onSuccess: () => {
                    toast.success('Valuation updated')
                    setEditValuationTarget(null)
                  },
                  onError: () => toast.error('Failed to update valuation'),
                },
              )
            }
            isSubmitting={updateValuation.isPending}
          />
        </EntityFormDialog>
      )}

      {/* Delete valuation */}
      {deleteValuationTarget && (
        <ConfirmDialog
          open={!!deleteValuationTarget}
          onOpenChange={(open) => {
            if (!open) setDeleteValuationTarget(null)
          }}
          title="Delete valuation?"
          description={`Date: ${formatDate(
            deleteValuationTarget.capital_structure_date,
          )}`}
          confirmText="Delete"
          confirmVariant="destructive"
          isLoading={deleteValuation.isPending}
          onConfirm={() => {
            deleteValuation.mutate(deleteValuationTarget.id, {
              onSuccess: () => {
                toast.success('Valuation deleted')
                setDeleteValuationTarget(null)
              },
              onError: () => toast.error('Failed to delete valuation'),
            })
          }}
        />
      )}
    </div>
  )
}

// ---- Helpers ---------------------------------------------------------------

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick}>
      <ArrowLeft className="h-4 w-4" />
      Back to properties
    </Button>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

function PropertyDetailSkeleton() {
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
