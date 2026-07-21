// frontend/src/components/table/DataTable.tsx
//
// Generic TanStack Table wrapper used by every B2 list page
// (Properties, Tenants, Transactions, Property Valuations).
//
// Concerns:
//   - Sorting (clickable headers toggle asc/desc; the header renderer
//     is owned by the caller via `ColumnDef.header`).
//   - Client-side pagination with a configurable `pageSize`.
//   - Row click for navigation/edit hand-off (cursor pointer hint).
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

type Props<T> = {
  columns: ColumnDef<T, any>[]
  data: T[]
  onRowClick?: (row: T) => void
  pageSize?: number
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
                className={onRowClick ? 'cursor-pointer' : ''}
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
      <div className="flex items-center justify-end space-x-2 py-4">
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
  )
}
