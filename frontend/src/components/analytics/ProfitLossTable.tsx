import { formatAccounting } from '@/lib/format'
import type { ProfitLossResponse } from '@/types/analytics'
import { cn } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type ProfitLossTableProps = {
  data: ProfitLossResponse
}

export function ProfitLossTable({ data }: ProfitLossTableProps) {
  return (
    <Table aria-label="Profit and Loss statement" className="min-w-max">
      <TableHeader>
        <TableRow>
          <TableHead className="sticky left-0 z-20 min-w-32 bg-card sm:min-w-44">
            Category
          </TableHead>
          {data.columns.map((column) => (
            <TableHead key={column.key} className="min-w-24 text-right sm:min-w-28">
              {column.label}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.rows.map((row, index) => {
          const previous = data.rows[index - 1]
          const isTotal = !['income', 'expense'].includes(row.kind)
          const startsExpenseBlock = row.kind === 'expense' && previous?.kind === 'total_revenue'
          return (
            <TableRow
              key={row.key}
              className={cn(
                isTotal && 'border-t font-semibold',
                startsExpenseBlock && 'border-t-8 border-t-muted',
              )}
            >
              <th
                scope="row"
                className={cn(
                  'sticky left-0 z-10 bg-card p-2 text-left align-middle whitespace-nowrap',
                  !isTotal && 'font-normal',
                )}
              >
                {row.label}
              </th>
              {data.columns.map((column) => (
                <TableCell
                  key={column.key}
                  className="text-right tabular-nums"
                >
                  {formatAccounting(row.values[column.key], data.currency)}
                </TableCell>
              ))}
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
