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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatAccounting, formatCurrency, formatDate } from '@/lib/format'
import type { PropertyValuation } from '@/types/propertyValuation'

// Number of recent transactions shown in the Overview tab. The full list
// lives on the Transactions page; the detail page only surfaces the most
// recent activity for at-a-glance context.
const RECENT_TRANSACTIONS_LIMIT = 5

// Income vs expense classification — mirrors `rentals/constants.py`.
// Only `rent` is income; `cost_reimbursement` (formerly `other_income`)
// is an expense-category offset (positive amount that nets against the
// other expense categories).
const INCOME_CATEGORIES = ['rent']

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

  // Latest valuation = highest capital_structure_date. Surfaced at the top
  // of the header card so users see the current property value next to the
  // name (the rest of the card carries bedrooms / area / status). When no
  // valuation exists yet we render an em-dash placeholder.
  const latestValuation = useMemo(() => {
    const list = valuationsQuery.data ?? []
    if (list.length === 0) return null
    return [...list].sort((a, b) =>
      a.capital_structure_date < b.capital_structure_date ? 1 : -1,
    )[0]
  }, [valuationsQuery.data])
  const latestValue = latestValuation
    ? Number(latestValuation.capital_structure_value)
    : null

  // P&L breakdown computed client-side from the property's transactions.
  // `Transaction.amount` is a stringified decimal (positive = income,
  // negative = expense); we group by category and split into all-time vs
  // YTD windows so the P&L table matches the dashboard's two-column
  // layout. The backend `chart-data` `property` branch only emits Debt +
  // Equity (it does not emit per-category totals), so we derive the P&L
  // here from the already-fetched transactions list rather than firing a
  // chart-data round-trip that would return empty categories.
  const pnlRows = useMemo(() => {
    const txns = transactionsQuery.data ?? []
    const currentYear = new Date().getFullYear()
    const byCatAll = new Map<string, number>()
    const byCatYtd = new Map<string, number>()
    for (const t of txns) {
      const amount = Number(t.amount)
      if (!Number.isFinite(amount)) continue
      const cat = t.category || 'other'
      byCatAll.set(cat, (byCatAll.get(cat) ?? 0) + amount)
      const year = parseInt(String(t.period || t.date).slice(0, 4), 10)
      if (year === currentYear) {
        byCatYtd.set(cat, (byCatYtd.get(cat) ?? 0) + amount)
      }
    }
    const isIncome = (label: string) => INCOME_CATEGORIES.includes(label)
    const build = (income: boolean, map: Map<string, number>) =>
      Array.from(map.entries())
        .filter(([label]) => isIncome(label) === income)
        // T12: drop categories with zero total so empty buckets (e.g.
        // `other_income` after the recategorization to
        // `cost_reimbursement`) don't appear as a stray row in the P&L.
        .filter(([, total]) => total !== 0)
        .map(([label, total]) => ({ label, total }))
    const incomeAll = build(true, byCatAll).sort((a, b) => a.label.localeCompare(b.label))
    const expenseAll = build(false, byCatAll).sort((a, b) => a.label.localeCompare(b.label))
    const incomeYtd = build(true, byCatYtd)
    const expenseYtd = build(false, byCatYtd)
    const totalIncomeAll = incomeAll.reduce((acc, r) => acc + r.total, 0)
    const totalIncomeYtd = incomeYtd.reduce((acc, r) => acc + r.total, 0)
    const totalExpenseAll = expenseAll.reduce((acc, r) => acc + r.total, 0)
    const totalExpenseYtd = expenseYtd.reduce((acc, r) => acc + r.total, 0)
    return {
      incomeAll,
      expenseAll,
      incomeYtd,
      expenseYtd,
      totalIncomeAll,
      totalIncomeYtd,
      totalExpenseAll,
      totalExpenseYtd,
      netIncomeAll: totalIncomeAll + totalExpenseAll,
      netIncomeYtd: totalIncomeYtd + totalExpenseYtd,
    }
  }, [transactionsQuery.data])

  // Most-recent first; the API may or may not pre-sort, so we sort here to
  // make the preview deterministic regardless of backend ordering. Capped
  // at RECENT_TRANSACTIONS_LIMIT so the panel stays a "recent activity"
  // summary — the full list lives on the Transactions page.
  const recentTransactions = useMemo(() => {
    const txns = [...(transactionsQuery.data ?? [])]
    txns.sort((a, b) => b.date.localeCompare(a.date))
    return txns.slice(0, RECENT_TRANSACTIONS_LIMIT)
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
            {/* Task 13: current property value (latest valuation) shown at
                the top in the property's native currency. Falls back to
                an em-dash when no valuation has been recorded yet — the
                Valuations tab is where the user creates one. */}
            <Stat
              label={`Value (${property.currency})`}
              value={
                latestValue !== null && Number.isFinite(latestValue)
                  ? formatCurrency(latestValue, property.currency)
                  : '—'
              }
            />
            <Stat label="Currency" value={property.currency} />
            <Stat label="Bedrooms" value={String(property.num_bedrooms)} />
            <Stat
              label="Area"
              value={property.area ? `${property.area} m²` : '—'}
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
                Per-category breakdown, all-time + YTD. All values in{' '}
                {property.currency}. Expenses show as{' '}
                <code className="rounded bg-muted px-1">{property.currency}(1,234)</code>{' '}
                (accounting format).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Per-category P&L table. Two columns (All-time + YTD).
                  Income categories first, then "Total revenue", then
                  expense categories (kept negative), then "Total
                  expenses" and "Net income". Derived client-side from
                  the property's transactions (the chart-data `property`
                  branch only emits Debt + Equity, not category totals). */}
              {transactionsQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : transactionsQuery.isError ? (
                <ErrorState
                  message="Failed to load P&L"
                  onRetry={() => transactionsQuery.refetch()}
                />
              ) : pnlRows.incomeAll.length === 0 &&
                pnlRows.expenseAll.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No category data available for this property yet.
                </p>
              ) : (
                <PropertyPnLTable rows={pnlRows} currency={property.currency} />
              )}
            </CardContent>
          </Card>

          {/* Rent yield chart (Plan C). Sits between the P&L card and the
              recent-transactions table so the yield trend is visible right
              after the summary numbers it derives from. The chart owns its
              own loading/error states via ChartCard; we pass the already-
              loaded property transactions through (the chart-data
              `property` branch only emits Debt + Equity, not per-category
              rent, so yield must be derived from transactions). The chart
              fetches its own valuations internally via
              usePropertyValuations. */}
          <RentYieldChart
            transactions={transactionsQuery.data ?? []}
            propertyId={propertyId}
            currency={property.currency}
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
              /* Task 17: filter is already applied via `useTransactions({
                 property: id })`; pagination is removed (rendered as a plain
                 <Table> limited client-side to the last 20 — the full list
                 lives on the Transactions page). */
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
                        <TableCell className="capitalize">{t.category}</TableCell>
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

          {/* Valuation chart (Plan C). Rendered ABOVE the capital-structure
              table so the trend is the first thing the user reads, with the
              raw rows below for detail. The chart-data request feeds Debt +
              Equity series; the chart overlays the sum (total value) as a
              line. Currency comes from the property's native currency. */}
          <ValuationChart
            data={chartQuery.data ?? { labels: [], datasets: [], currency: property.currency }}
            currency={property.currency}
          />

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

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  )
}

// Per-property P&L table. Two columns (All-time + YTD), same layout as
// the dashboard P&L: income categories first, then "Total revenue", then
// expense categories (kept negative), then "Total expenses" and
// "Net income". `formatAccounting` renders negatives as `(1,234)` so the
// sign convention is unambiguous. Rows are derived client-side from the
// property's transactions (see `pnlRows` above).
type PropertyPnLCategoryRow = { label: string; total: number }

type PropertyPnLRows = {
  incomeAll: PropertyPnLCategoryRow[]
  expenseAll: PropertyPnLCategoryRow[]
  incomeYtd: PropertyPnLCategoryRow[]
  expenseYtd: PropertyPnLCategoryRow[]
  totalIncomeAll: number
  totalIncomeYtd: number
  totalExpenseAll: number
  totalExpenseYtd: number
  netIncomeAll: number
  netIncomeYtd: number
}

function PropertyPnLTable({
  rows,
  currency,
}: {
  rows: PropertyPnLRows
  currency: string
}) {
  const ytdFor = (ytdRows: PropertyPnLCategoryRow[], label: string) =>
    ytdRows.find((r) => r.label === label)?.total ?? 0
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Category</TableHead>
            <TableHead className="text-right">All time</TableHead>
            <TableHead className="text-right">YTD</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* Income rows */}
          {rows.incomeAll.map((row) => (
            <TableRow key={`income-${row.label}`}>
              <TableCell className="font-medium capitalize">
                {row.label}
              </TableCell>
              <TableCell className="text-right">
                {formatAccounting(row.total, currency)}
              </TableCell>
              <TableCell className="text-right">
                {formatAccounting(ytdFor(rows.incomeYtd, row.label), currency)}
              </TableCell>
            </TableRow>
          ))}
          {/* Total revenue */}
          <TableRow className="border-t">
            <TableCell className="font-bold">Total revenue</TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.totalIncomeAll, currency)}
            </TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.totalIncomeYtd, currency)}
            </TableCell>
          </TableRow>
          {/* Expense rows — kept negative so formatAccounting renders
              brackets. */}
          {rows.expenseAll.map((row) => (
            <TableRow key={`expense-${row.label}`}>
              <TableCell className="font-medium capitalize">
                {row.label}
              </TableCell>
              <TableCell className="text-right">
                {formatAccounting(row.total, currency)}
              </TableCell>
              <TableCell className="text-right">
                {formatAccounting(ytdFor(rows.expenseYtd, row.label), currency)}
              </TableCell>
            </TableRow>
          ))}
          {/* Total expenses (kept negative). */}
          <TableRow className="border-t">
            <TableCell className="font-bold">Total expenses</TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.totalExpenseAll, currency)}
            </TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.totalExpenseYtd, currency)}
            </TableCell>
          </TableRow>
          {/* Net income */}
          <TableRow className="border-t-2">
            <TableCell className="font-bold">Net income</TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.netIncomeAll, currency)}
            </TableCell>
            <TableCell className="text-right font-bold">
              {formatAccounting(rows.netIncomeYtd, currency)}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
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
