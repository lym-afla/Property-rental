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
const INCOME_CATEGORIES = ['rent', 'other_income']

// Whitelist of valid transaction categories (mirrors
// `rentals/constants.py::TRANSACTION_CATEGORIES`). The property
// chart-data endpoint returns Debt + Equity datasets (for the
// ValuationChart), which would otherwise leak into the P&L table as
// bogus "expense" rows. Filtering to this whitelist keeps the P&L
// limited to real transaction categories.
const TRANSACTION_CATEGORY_KEYS = [
  'rent',
  'tax',
  'capex',
  'management',
  'electricity',
  'utilities',
  'internet',
  'other_income',
  'other_expenses',
]

function isTransactionCategory(label: string): boolean {
  return TRANSACTION_CATEGORY_KEYS.includes(label)
}

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

  // Annual P&L chart-data request (for the per-year + YTD P&L table).
  // Five-year window matches the chart history; labels come back as
  // `2022`, `2023`, ... and one dataset per category. YTD is computed
  // client-side against the current year's transactions.
  const annualPnlQuery = useChartData({
    type: 'property',
    elementId: propertyId,
    frequency: 'Y',
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
  // make the preview deterministic regardless of backend ordering. Capped
  // at RECENT_TRANSACTIONS_LIMIT so the panel stays a "recent activity"
  // summary — the full list lives on the Transactions page.
  const recentTransactions = useMemo(() => {
    const txns = [...(transactionsQuery.data ?? [])]
    txns.sort((a, b) => b.date.localeCompare(a.date))
    return txns.slice(0, RECENT_TRANSACTIONS_LIMIT)
  }, [transactionsQuery.data])

  // Annual + YTD P&L table (Task 14). The annual chart-data response gives
  // us one dataset per category with `data[i]` aligned to `labels[i]`
  // (year strings). We pivot that into a per-category row keyed by year,
  // plus a synthetic "YTD" column derived from the current year's slice
  // of the same dataset (the chart-data service clamps the upper bound
  // to today for `property`-typed requests, so the last column is YTD).
  const pnlTable = useMemo(() => {
    const labels = annualPnlQuery.data?.labels ?? []
    const datasets = annualPnlQuery.data?.datasets ?? []
    const years = labels.filter((l) => /^\d{4}$/.test(String(l)))
    // YTD column — current calendar year. If the response already
    // includes the current year, treat its value as YTD; otherwise show
    // em-dashes per row (no data yet this year).
    const currentYear = String(new Date().getFullYear())
    const ytdInLabels = years.includes(currentYear)

    const isIncome = (label: string) => INCOME_CATEGORIES.includes(label)
    const categoryRows: {
      label: string
      isIncome: boolean
      byYear: Record<string, number>
      ytd: number
    }[] = []

    for (const ds of datasets) {
      const label = ds.label ?? ''
      if (label === '') continue // skip unlabeled "value" series
      // Skip non-transaction datasets (the property chart-data endpoint
      // also returns Debt + Equity series for the ValuationChart; those
      // are not P&L categories and must not appear here).
      if (!isTransactionCategory(label)) continue
      const byYear: Record<string, number> = {}
      for (let i = 0; i < years.length; i++) {
        const year = years[i]
        byYear[year] = Number(ds.data?.[i] ?? 0)
      }
      // YTD = the current year's column if present, else 0.
      const ytd = ytdInLabels ? Number(byYear[currentYear] ?? 0) : 0
      categoryRows.push({ label, isIncome: isIncome(label), byYear, ytd })
    }

    // Stable sort: income categories first (canonical order), then
    // expenses alphabetically.
    categoryRows.sort((a, b) => {
      if (a.isIncome !== b.isIncome) return a.isIncome ? -1 : 1
      return a.label.localeCompare(b.label)
    })

    // Totals per year + YTD.
    const totalIncomeByYear: Record<string, number> = {}
    const totalExpenseByYear: Record<string, number> = {}
    let totalIncomeYtd = 0
    let totalExpenseYtd = 0
    for (const year of years) {
      totalIncomeByYear[year] = categoryRows
        .filter((r) => r.isIncome)
        .reduce((acc, r) => acc + (r.byYear[year] ?? 0), 0)
      totalExpenseByYear[year] = categoryRows
        .filter((r) => !r.isIncome)
        .reduce((acc, r) => acc + (r.byYear[year] ?? 0), 0)
    }
    totalIncomeYtd = categoryRows
      .filter((r) => r.isIncome)
      .reduce((acc, r) => acc + r.ytd, 0)
    totalExpenseYtd = categoryRows
      .filter((r) => !r.isIncome)
      .reduce((acc, r) => acc + r.ytd, 0)

    return {
      years,
      currentYear,
      ytdInLabels,
      categoryRows,
      totalIncomeByYear,
      totalExpenseByYear,
      totalIncomeYtd,
      totalExpenseYtd,
    }
  }, [annualPnlQuery.data])

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
                Per-category breakdown by year + YTD. All values in{' '}
                {property.currency}.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Headline summary tiles — gross income / expenses / net for
                  the property's lifetime. Mirrors the previous P&L card so
                  the at-a-glance numbers stay above the new detailed table. */}
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <Stat
                  label="Gross income (all-time)"
                  value={formatCurrency(pnl.income, property.currency)}
                />
                <Stat
                  label="Expenses (all-time)"
                  value={formatCurrency(pnl.expenses, property.currency)}
                />
                <Stat
                  label="Net income (all-time)"
                  value={formatCurrency(pnl.net, property.currency)}
                />
              </dl>

              {/* Annual + YTD breakdown table (Task 14). One row per
                  category, one column per year (last 5), plus a YTD
                  column. Totals at the bottom. Renders an em-dash cell
                  when the chart-data response has no data for a year. */}
              {annualPnlQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : annualPnlQuery.isError ? (
                <ErrorState
                  message="Failed to load annual P&L"
                  onRetry={() => annualPnlQuery.refetch()}
                />
              ) : pnlTable.categoryRows.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No category data available for this property yet.
                </p>
              ) : (
                <PnLTable
                  years={pnlTable.years}
                  rows={pnlTable.categoryRows}
                  totalIncomeByYear={pnlTable.totalIncomeByYear}
                  totalExpenseByYear={pnlTable.totalExpenseByYear}
                  totalIncomeYtd={pnlTable.totalIncomeYtd}
                  totalExpenseYtd={pnlTable.totalExpenseYtd}
                  currency={property.currency}
                />
              )}
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
              overlays the sum (total value) as a line. Currency comes from
              the property's native currency (Task 19). */}
          <ValuationChart
            data={chartQuery.data ?? { labels: [], datasets: [], currency: property.currency }}
            currency={property.currency}
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

// Annual P&L table (Task 14). Renders one row per category (income first,
// then expenses), a Total income / Total expenses pair, and a Net income
// row. Columns are the years returned by the chart-data request plus a
// YTD column at the end (YTD = the current year's column from the same
// response, since chart-data clamps the upper bound to today).
type PnLRow = {
  label: string
  isIncome: boolean
  byYear: Record<string, number>
  ytd: number
}

function PnLTable({
  years,
  rows,
  totalIncomeByYear,
  totalExpenseByYear,
  totalIncomeYtd,
  totalExpenseYtd,
  currency,
}: {
  years: string[]
  rows: PnLRow[]
  totalIncomeByYear: Record<string, number>
  totalExpenseByYear: Record<string, number>
  totalIncomeYtd: number
  totalExpenseYtd: number
  currency: string
}) {
  const headers = [...years, 'YTD']
  const incomeRows = rows.filter((r) => r.isIncome)
  const expenseRows = rows.filter((r) => !r.isIncome)
  const netByYear: Record<string, number> = {}
  for (const year of years) {
    netByYear[year] =
      (totalIncomeByYear[year] ?? 0) + (totalExpenseByYear[year] ?? 0)
  }
  const netYtd = totalIncomeYtd + totalExpenseYtd

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Category</TableHead>
            {headers.map((h) => (
              <TableHead key={h} className="text-right">
                {h}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* Income rows */}
          {incomeRows.map((row) => (
            <TableRow key={`income-${row.label}`}>
              <TableCell className="font-medium capitalize">
                {row.label}
              </TableCell>
              {headers.map((h) => (
                <TableCell key={h} className="text-right">
                  {h === 'YTD'
                    ? formatCurrency(Math.abs(row.ytd), currency)
                    : formatCurrency(
                        Math.abs(row.byYear[h] ?? 0),
                        currency,
                      )}
                </TableCell>
              ))}
            </TableRow>
          ))}
          {/* Expense rows — display the absolute value (chart-data returns
              negatives for expenses). */}
          {expenseRows.map((row) => (
            <TableRow key={`expense-${row.label}`}>
              <TableCell className="font-medium capitalize">
                {row.label}
              </TableCell>
              {headers.map((h) => (
                <TableCell key={h} className="text-right">
                  {h === 'YTD'
                    ? formatCurrency(Math.abs(row.ytd), currency)
                    : formatCurrency(
                        Math.abs(row.byYear[h] ?? 0),
                        currency,
                      )}
                </TableCell>
              ))}
            </TableRow>
          ))}
          {/* Totals */}
          <TableRow className="border-t-2">
            <TableCell className="font-bold">Total income</TableCell>
            {headers.map((h) => (
              <TableCell key={h} className="text-right font-bold">
                {h === 'YTD'
                  ? formatCurrency(totalIncomeYtd, currency)
                  : formatCurrency(totalIncomeByYear[h] ?? 0, currency)}
              </TableCell>
            ))}
          </TableRow>
          <TableRow>
            <TableCell className="font-bold">Total expenses</TableCell>
            {headers.map((h) => (
              <TableCell key={h} className="text-right font-bold">
                {h === 'YTD'
                  ? formatCurrency(Math.abs(totalExpenseYtd), currency)
                  : formatCurrency(
                      Math.abs(totalExpenseByYear[h] ?? 0),
                      currency,
                    )}
              </TableCell>
            ))}
          </TableRow>
          <TableRow className="border-t-2">
            <TableCell className="font-bold">Net income</TableCell>
            {headers.map((h) => (
              <TableCell key={h} className="text-right font-bold">
                {h === 'YTD'
                  ? formatCurrency(netYtd, currency)
                  : formatCurrency(netByYear[h] ?? 0, currency)}
              </TableCell>
            ))}
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
