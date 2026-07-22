// frontend/src/components/table/DataTable.tsx
//
// Generic TanStack Table wrapper used by every B2 list page
// (Properties, Tenants, Transactions, Property Valuations).
//
// Concerns:
//   - Sorting (clickable headers toggle asc/desc; the header renderer
//     is owned by the caller via `ColumnDef.header`).
//   - Client-side pagination with a configurable `pageSize` AND a
//     user-facing "Items per page" selector (10 / 25 / 50 / 100). The
//     selector calls `table.setPageSize`; the underlying React Table
//     instance carries the choice across sorts / re-renders.
//   - Row click for navigation/edit hand-off (cursor pointer hint).
//   - Optional per-row className hook so callers can shade rows based
//     on row data (e.g. TenantsPage greys out vacated tenants).
//
// The generic constraint `<T extends { id: number }>` matches every
// entity shape we serialize from the backend (Property, Tenant,
// Transaction, PropertyValuation) — they all carry a numeric `id`.
import { useState } from 'react'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

// Page-size options surfaced in the "Items per page" selector. 10 is the
// default for every page that doesn't override via `pageSize`.
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100] as const

type Props<T> = {
  columns: ColumnDef<T, any>[]
  data: T[]
  onRowClick?: (row: T) => void
  pageSize?: number
  // Optional hook letting callers tag individual rows with extra classes
  // (e.g. `opacity-60 bg-muted/40` for vacated tenants). Default returns
  // an empty string.
  getRowClassName?: (row: T) => string
  // Initial controlled sorting state (e.g. `[{ id: 'date', desc: true }]`
  // to default to latest-first). The state is still controlled — the user
  // can toggle it via the headers from there.
  initialSorting?: SortingState
}

export function DataTable<T extends { id: number }>({
  columns,
  data,
  onRowClick,
  pageSize = 10,
  getRowClassName,
  initialSorting = [],
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>(initialSorting)
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  })

  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => (
                  <TableHead key={header.id}>
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                onClick={() => onRowClick?.(row.original)}
                className={[
                  onRowClick ? 'cursor-pointer' : '',
                  getRowClassName?.(row.original) ?? '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext(),
                    )}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between gap-4 py-4">
        {/* Items per page selector — TanStack supports `setPageSize`
            natively; we wrap it in a labeled <Select>. */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Items per page</span>
          <Select
            value={String(table.getState().pagination.pageSize)}
            onValueChange={(v) => table.setPageSize(Number(v))}
          >
            <SelectTrigger className="h-8 w-[80px]" aria-label="Items per page">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">
            {table.getState().pagination.pageIndex + 1} /{' '}
            {Math.max(table.getPageCount(), 1)}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
