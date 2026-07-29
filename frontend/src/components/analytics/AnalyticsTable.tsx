import type { ReactNode } from 'react'

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { cn } from '@/lib/utils'

export type AnalyticsTableColumn = {
  key: string
  label: string
  numeric?: boolean
}

export type AnalyticsTableRow = Record<string, ReactNode>

type AnalyticsTableProps = {
  label: string
  columns: readonly AnalyticsTableColumn[]
  rows: readonly AnalyticsTableRow[]
}

export function AnalyticsTable({ label, columns, rows }: AnalyticsTableProps) {
  return (
    <div data-testid="analytics-table-overflow" className="relative w-full overflow-x-auto">
      <Table aria-label={label} className="min-w-max tabular-nums">
        <TableHeader>
          <TableRow>
            {columns.map((column, index) => (
              <TableHead
                key={column.key}
                className={cn(
                  column.numeric && 'text-right',
                  index === 0 && 'sticky left-0 z-10 bg-card',
                )}
              >
                {column.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, rowIndex) => (
            <TableRow key={rowIndex}>
              {columns.map((column, index) => (
                <TableCell
                  key={column.key}
                  className={cn(
                    column.numeric && 'text-right',
                    index === 0 && 'sticky left-0 z-10 bg-card font-medium',
                  )}
                >
                  {row[column.key] ?? '—'}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
