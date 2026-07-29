// frontend/src/components/charts/PaginatedTable.tsx
//
// Minimal paginated table for chart "view as table" payloads. ChartCard's
// default table renderer just dumps every row in one scrollable <Table>;
// for series with hundreds of periods (e.g. monthly rent history over a
// long tenancy) that's unreadable. This component wraps the same header/
// rows shape with simple Prev/Next pagination.
//
// It deliberately avoids the generic `DataTable` (which carries
// TanStack sorting, page-size selector, and a `{ id: number }` row-type
// constraint) — chart rows are heterogeneous `string | number` cells and
// don't have stable ids, so a leaner table is a better fit.
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type Props = {
  headers: string[]
  rows: (string | number)[][]
  // Optional per-row formatter. Maps each raw cell to a displayable
  // value (string | number | ReactNode-compatible). Useful when the
  // underlying row carries a raw numeric that needs currency or percent
  // formatting (e.g. tenant rent history amounts, rent yield %).
  formatRow?: (row: (string | number)[]) => (string | number)[]
  pageSize?: number
}

export function PaginatedTable({
  headers,
  rows,
  formatRow,
  pageSize = 10,
}: Props) {
  const [pageIndex, setPageIndex] = useState(0)
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize))
  const safePageIndex = Math.min(pageIndex, pageCount - 1)
  const start = safePageIndex * pageSize
  const pageRows = rows.slice(start, start + pageSize)

  return (
    <div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {headers.map((h) => (
                <TableHead key={h}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={headers.length}
                  className="text-sm text-muted-foreground"
                >
                  No data.
                </TableCell>
              </TableRow>
            ) : (
              pageRows.map((row, i) => {
                const cells = formatRow ? formatRow(row) : row
                return (
                  <TableRow key={start + i}>
                    {cells.map((cell, j) => (
                      <TableCell key={j}>{cell}</TableCell>
                    ))}
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end gap-2 py-3">
        <span className="text-sm text-muted-foreground">
          {safePageIndex + 1} / {pageCount}
        </span>
        <Button
          variant="outline"
          size="sm"
          className="min-h-11"
          onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
          disabled={safePageIndex === 0}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="min-h-11"
          onClick={() => setPageIndex((p) => Math.min(pageCount - 1, p + 1))}
          disabled={safePageIndex >= pageCount - 1}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
