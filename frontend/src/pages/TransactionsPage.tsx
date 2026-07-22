// frontend/src/pages/TransactionsPage.tsx
//
// Transactions list page (Task 6 of Plan B2).
//
// Consumes the B1 hooks + components:
//   - `useTransactions({ property, tenant, category, start, end })` for the
//     table rows. The hook sends those filters as query params to
//     `/api/v1/transactions/`, which the DRF ViewSet filters on.
//   - `useProperties` + `useTenants` to populate the filter dropdowns and the
//     create dialog's property/tenant selects.
//   - `useCreateTransaction` wired into `EntityFormDialog` via
//     `TransactionForm`. The form's tenant select cascades off the selected
//     property (B1 Task 11); the page just feeds the lists.
//   - `DataTable`, `SkeletonTable`, `EmptyState`, `ErrorState`.
//
// URL-synced filters (Plan C drill-down target):
//   - On mount we read `useSearchParams` for `property`, `tenant`,
//     `category`, `from`, `to`, `search` and seed the local filter state.
//   - Whenever any filter changes we push the new value back into the URL
//     (without scrolling) so the location is shareable and survives reload.
//   - Empty values are deleted from the URL rather than serialized as empty
//     strings (avoids `?property=&...` noise in the share link).
//
// The `search` filter is client-side: the backend ViewSet does not expose a
// `q=` filter, so we match against `comment`/`category` locally after the
// fetch resolves. Other filters are server-side.
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { type ColumnDef } from '@tanstack/react-table'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  useTransactions,
  useCreateTransaction,
  useUpdateTransaction,
  useDeleteTransaction,
} from '@/api/transactions'
import { useProperties } from '@/api/properties'
import { useTenants } from '@/api/tenants'
import { DataTable } from '@/components/table/DataTable'
import { EntityFormDialog } from '@/components/modals/EntityFormDialog'
import { ConfirmDialog } from '@/components/modals/ConfirmDialog'
import { TransactionForm, TRANSACTION_CATEGORY_OPTIONS } from '@/components/forms/TransactionForm'
import { SkeletonTable } from '@/components/states/SkeletonTable'
import { EmptyState } from '@/components/states/EmptyState'
import { ErrorState } from '@/components/states/ErrorState'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatAccounting, formatCurrency, formatDate } from '@/lib/format'
import type { Transaction } from '@/types/transaction'
import type { Property } from '@/types/property'
import type { Tenant } from '@/types/tenant'

// Sentinel value used by the filter `<Select>` for "no filter selected".
// Radix Select can't represent an empty string as a value, so we use a
// dedicated sentinel and treat it as "all" below.
const ALL_FILTER = '__all__'

// Filter state held in component state. `property`/`tenant` are numbers or
// undefined; `category` is one of the canonical category strings or
// undefined; `from`/`to` are `YYYY-MM-DD` strings or undefined; `search` is
// free text.
type Filters = {
  property?: number
  tenant?: number
  category?: string
  from?: string
  to?: string
  search?: string
}

// Pull a numeric param out of the URL, returning undefined for missing or
// non-numeric values.
function numParam(value: string | null): number | undefined {
  if (!value) return undefined
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : undefined
}

// Read the initial filter set from the URL on mount.
function readFiltersFromURL(params: URLSearchParams): Filters {
  return {
    property: numParam(params.get('property')),
    tenant: numParam(params.get('tenant')),
    category: params.get('category') ?? undefined,
    from: params.get('from') ?? undefined,
    to: params.get('to') ?? undefined,
    search: params.get('search') ?? undefined,
  }
}

// Serialize the active filters back to the URL. Empty/undefined values are
// dropped so the share link stays minimal.
function writeFiltersToURL(filters: Filters, setSearchParams: (next: URLSearchParams, opts: { replace: boolean }) => void) {
  const next = new URLSearchParams()
  if (filters.property) next.set('property', String(filters.property))
  if (filters.tenant) next.set('tenant', String(filters.tenant))
  if (filters.category) next.set('category', filters.category)
  if (filters.from) next.set('from', filters.from)
  if (filters.to) next.set('to', filters.to)
  if (filters.search) next.set('search', filters.search)
  setSearchParams(next, { replace: true })
}

export function TransactionsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Seed the filter state once from the URL on first render. Subsequent
  // changes flow URL -> state here; state -> URL via `writeFiltersToURL`.
  const [filters, setFilters] = useState<Filters>(() =>
    readFiltersFromURL(searchParams),
  )

  // Push filter changes back to the URL whenever they change. Using
  // `replace: true` keeps the history tidy — every keystroke in the search
  // box would otherwise create a new back-button entry.
  useEffect(() => {
    writeFiltersToURL(filters, setSearchParams)
    // We intentionally depend only on `filters`; `setSearchParams` is a
    // stable identity from react-router.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  const transactionsQuery = useTransactions({
    property: filters.property,
    tenant: filters.tenant,
    category: filters.category,
    start: filters.from,
    end: filters.to,
  })
  const propertiesQuery = useProperties()
  const tenantsQuery = useTenants()
  const createTransaction = useCreateTransaction()
  const updateTransaction = useUpdateTransaction()
  const deleteTransaction = useDeleteTransaction()

  const [createOpen, setCreateOpen] = useState(false)
  // Edit target: when set, the edit dialog renders with this transaction's
  // values pre-filled. Cleared on dialog close.
  const [editTarget, setEditTarget] = useState<Transaction | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Transaction | null>(null)

  // Build lookup maps for the property/tenant display columns.
  const propertyById = useMemo(() => {
    const map = new Map<number, Property>()
    for (const p of propertiesQuery.data ?? []) map.set(p.id, p)
    return map
  }, [propertiesQuery.data])

  const tenantById = useMemo(() => {
    const map = new Map<number, Tenant>()
    for (const t of tenantsQuery.data ?? []) map.set(t.id, t)
    return map
  }, [tenantsQuery.data])

  // The `search` filter is client-side (no backend `q=` param). Match the
  // raw query against category + comment so users can find e.g. "rent" or
  // "leak" quickly. Case-insensitive; empty query passes everything.
  const visibleTransactions = useMemo(() => {
    const rows = transactionsQuery.data ?? []
    const q = filters.search?.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((t) => {
      const comment = (t.comment ?? '').toLowerCase()
      const category = (t.category ?? '').toLowerCase()
      return comment.includes(q) || category.includes(q)
    })
  }, [transactionsQuery.data, filters.search])

  const columns: ColumnDef<Transaction>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      // `sortingFn: 'datetime'` so TanStack compares the rows as dates
      // rather than lexical strings — correct ordering across year
      // boundaries even when the field is a `YYYY-MM-DD` string.
      sortingFn: 'datetime',
      cell: ({ row }) => formatDate(row.original.date),
    },
    {
      id: 'property',
      header: 'Property',
      cell: ({ row }) => {
        const p = propertyById.get(row.original.property)
        return p?.name ?? `#${row.original.property}`
      },
    },
    {
      id: 'tenant',
      header: 'Tenant',
      // Tenant names come from the lookup map; if the FK is null (a
      // property-level transaction with no tenant assigned) we render an
      // em dash instead of "null" / "undefined".
      cell: ({ row }) => {
        if (row.original.tenant == null) return '—'
        const t = tenantById.get(row.original.tenant)
        if (!t) return `#${row.original.tenant}`
        const last = t.last_name ?? ''
        if (!last) return t.first_name ?? '—'
        return `${t.first_name} ${last}`
      },
    },
    { accessorKey: 'category', header: 'Category' },
    {
      accessorKey: 'amount',
      header: 'Amount',
      // Accounting format: negatives render as `(1,234)` (matching the
      // old Django template's treatment of expenses); positives use the
      // plain `#,###` form. The symbol is omitted because the column
      // header doesn't pin a single currency (rows can be in any of the
      // property currencies); the currency lives in the row's own
      // `currency` field and surfaces in the delete confirmation dialog.
      cell: ({ row }) => formatAccounting(row.original.amount),
    },
    {
      accessorKey: 'period',
      header: 'Period',
    },
    {
      accessorKey: 'comment',
      header: 'Comment',
      cell: ({ row }) => row.original.comment ?? '—',
    },
    {
      id: 'actions',
      header: 'Actions',
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Edit transaction ${row.original.id}`}
            onClick={(e) => {
              e.stopPropagation()
              setEditTarget(row.original)
            }}
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label={`Delete transaction ${row.original.id}`}
            onClick={(e) => {
              e.stopPropagation()
              setDeleteTarget(row.original)
            }}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ]

  // ---- Render guards -------------------------------------------------------

  if (transactionsQuery.isLoading) {
    return <SkeletonTable />
  }

  if (transactionsQuery.isError) {
    return (
      <ErrorState
        message="Failed to load transactions"
        onRetry={() => transactionsQuery.refetch()}
      />
    )
  }

  const isEmpty = !transactionsQuery.data || transactionsQuery.data.length === 0

  if (isEmpty) {
    return (
      <div className="space-y-4">
        <FilterBar
          filters={filters}
          onChange={setFilters}
          properties={propertiesQuery.data ?? []}
          tenants={tenantsQuery.data ?? []}
        />
        <EmptyState
          title="No transactions yet"
          description="Record your first rent payment or expense to get started."
          actionLabel="New Transaction"
          onAction={() => setCreateOpen(true)}
        />
        <EntityFormDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          title="Transaction"
          mode="create"
        >
          <TransactionForm
            properties={propertiesQuery.data ?? []}
            tenants={tenantsQuery.data ?? []}
            onSubmit={(values) =>
              createTransaction.mutate(values, {
                onSuccess: () => {
                  toast.success('Transaction created')
                  setCreateOpen(false)
                },
                onError: () => toast.error('Failed to create transaction'),
              })
            }
            isSubmitting={createTransaction.isPending}
          />
        </EntityFormDialog>
        {editTarget && (
          <EntityFormDialog
            open={!!editTarget}
            onOpenChange={(open) => {
              if (!open) setEditTarget(null)
            }}
            title="Transaction"
            mode="edit"
          >
            <TransactionForm
              properties={propertiesQuery.data ?? []}
              tenants={tenantsQuery.data ?? []}
              defaultValues={{
                date: editTarget.date,
                property: editTarget.property,
                tenant: editTarget.tenant,
                category: editTarget.category as
                  | (typeof TRANSACTION_CATEGORY_OPTIONS)[number]
                  | undefined,
                amount: editTarget.amount,
                currency: editTarget.currency as never,
                comment: editTarget.comment ?? '',
              }}
              onSubmit={(values) =>
                updateTransaction.mutate(
                  { id: editTarget.id, data: values },
                  {
                    onSuccess: () => {
                      toast.success('Transaction updated')
                      setEditTarget(null)
                    },
                    onError: () => toast.error('Failed to update transaction'),
                  },
                )
              }
              isSubmitting={updateTransaction.isPending}
            />
          </EntityFormDialog>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Transactions</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Transaction
        </Button>
      </div>

      <FilterBar
        filters={filters}
        onChange={setFilters}
        properties={propertiesQuery.data ?? []}
        tenants={tenantsQuery.data ?? []}
      />

      <DataTable
        columns={columns}
        data={visibleTransactions}
        initialSorting={[{ id: 'date', desc: true }]}
      />

      <EntityFormDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        title="Transaction"
        mode="create"
      >
        <TransactionForm
          properties={propertiesQuery.data ?? []}
          tenants={tenantsQuery.data ?? []}
          onSubmit={(values) =>
            createTransaction.mutate(values, {
              onSuccess: () => {
                toast.success('Transaction created')
                setCreateOpen(false)
              },
              onError: () => toast.error('Failed to create transaction'),
            })
          }
          isSubmitting={createTransaction.isPending}
        />
      </EntityFormDialog>

      {editTarget && (
        <EntityFormDialog
          open={!!editTarget}
          onOpenChange={(open) => {
            if (!open) setEditTarget(null)
          }}
          title="Transaction"
          mode="edit"
        >
          <TransactionForm
            properties={propertiesQuery.data ?? []}
            tenants={tenantsQuery.data ?? []}
            defaultValues={{
              date: editTarget.date,
              property: editTarget.property,
              tenant: editTarget.tenant,
              category: editTarget.category as
                | (typeof TRANSACTION_CATEGORY_OPTIONS)[number]
                | undefined,
              amount: editTarget.amount,
              currency: editTarget.currency as never,
              comment: editTarget.comment ?? '',
            }}
            onSubmit={(values) =>
              updateTransaction.mutate(
                { id: editTarget.id, data: values },
                {
                  onSuccess: () => {
                    toast.success('Transaction updated')
                    setEditTarget(null)
                  },
                  onError: () => toast.error('Failed to update transaction'),
                },
              )
            }
            isSubmitting={updateTransaction.isPending}
          />
        </EntityFormDialog>
      )}

      {deleteTarget && (
        <ConfirmDialog
          open={!!deleteTarget}
          onOpenChange={(open) => {
            if (!open) setDeleteTarget(null)
          }}
          title="Delete transaction?"
          description={`${formatDate(deleteTarget.date)} · ${deleteTarget.category} · ${formatCurrency(Number(deleteTarget.amount), deleteTarget.currency)}`}
          confirmText="Delete"
          confirmVariant="destructive"
          isLoading={deleteTransaction.isPending}
          onConfirm={() => {
            if (!deleteTarget) return
            deleteTransaction.mutate(deleteTarget.id, {
              onSuccess: () => {
                toast.success('Transaction deleted')
                setDeleteTarget(null)
              },
              onError: () => toast.error('Failed to delete transaction'),
            })
          }}
        />
      )}
    </div>
  )
}

// ---- Filter bar -----------------------------------------------------------
//
// A compact horizontal bar of `<Select>`s and two `<Input type="date">` fields
// for the date range, plus a text search box. All controls are controlled by
// the parent's `filters` state, so the URL sync stays the single source of
// truth.

type FilterBarProps = {
  filters: Filters
  onChange: (next: Filters) => void
  properties: Property[]
  tenants: Tenant[]
}

function FilterBar({ filters, onChange, properties, tenants }: FilterBarProps) {
  // Narrow the tenant dropdown to the selected property so the filter UI
  // matches the create form's cascade. When no property is selected, show
  // every tenant.
  const tenantOptions = useMemo(() => {
    if (filters.property == null) return tenants
    return tenants.filter((t) => t.property === filters.property)
  }, [tenants, filters.property])

  return (
    <div className="grid grid-cols-1 gap-2 rounded-md border bg-card p-3 text-sm sm:grid-cols-2 lg:grid-cols-6">
      <FilterSelect
        label="Property"
        value={filters.property != null ? String(filters.property) : ALL_FILTER}
        onValueChange={(v) =>
          onChange({
            ...filters,
            property: v === ALL_FILTER ? undefined : Number(v),
            // Clear tenant if it doesn't belong to the new property.
            tenant:
              v !== ALL_FILTER && filters.tenant != null
                ? tenants.find((t) => t.id === filters.tenant && t.property === Number(v))
                  ? filters.tenant
                  : undefined
                : filters.tenant,
          })
        }
      >
        <SelectItem value={ALL_FILTER}>All properties</SelectItem>
        {properties.map((p) => (
          <SelectItem key={p.id} value={String(p.id)}>
            {p.name}
          </SelectItem>
        ))}
      </FilterSelect>

      <FilterSelect
        label="Tenant"
        value={filters.tenant != null ? String(filters.tenant) : ALL_FILTER}
        onValueChange={(v) =>
          onChange({
            ...filters,
            tenant: v === ALL_FILTER ? undefined : Number(v),
          })
        }
      >
        <SelectItem value={ALL_FILTER}>All tenants</SelectItem>
        {tenantOptions.map((t) => (
          <SelectItem key={t.id} value={String(t.id)}>
            {t.first_name} {t.last_name}
          </SelectItem>
        ))}
      </FilterSelect>

      <FilterSelect
        label="Category"
        value={filters.category ?? ALL_FILTER}
        onValueChange={(v) =>
          onChange({
            ...filters,
            category: v === ALL_FILTER ? undefined : v,
          })
        }
      >
        <SelectItem value={ALL_FILTER}>All categories</SelectItem>
        {TRANSACTION_CATEGORY_OPTIONS.map((c) => (
          <SelectItem key={c} value={c}>
            {c}
          </SelectItem>
        ))}
      </FilterSelect>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-muted-foreground">From</span>
        <Input
          type="date"
          value={filters.from ?? ''}
          onChange={(e) =>
            onChange({ ...filters, from: e.target.value || undefined })
          }
        />
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-muted-foreground">To</span>
        <Input
          type="date"
          value={filters.to ?? ''}
          onChange={(e) =>
            onChange({ ...filters, to: e.target.value || undefined })
          }
        />
      </label>

      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-muted-foreground">Search</span>
        <Input
          type="search"
          placeholder="comment or category"
          value={filters.search ?? ''}
          onChange={(e) =>
            onChange({ ...filters, search: e.target.value || undefined })
          }
        />
      </label>
    </div>
  )
}

// Small wrapper that adds a leading label to a shadcn `<Select>`. The label
// doubles as an accessible name (radix wires `aria-labelledby` implicitly
// when the trigger is focusable).
function FilterSelect({
  label,
  value,
  onValueChange,
  children,
}: {
  label: string
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-muted-foreground">{label}</span>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
    </label>
  )
}
